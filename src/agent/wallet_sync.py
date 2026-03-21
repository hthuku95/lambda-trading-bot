# src/agent/wallet_sync.py
"""
Wallet Synchronization Module
Handles external wallet modifications and keeps agent state in sync

Critical for situations where:
- User withdraws funds from wallet
- User deposits funds externally
- External transactions occur
- Multiple agents or systems use same wallet
"""
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("trading_agent.wallet_sync")


class WalletSyncManager:
    """
    Manages wallet state synchronization with agent state

    Prevents issues when wallet is modified externally
    """

    def __init__(self, tolerance_percentage: float = 5.0):
        """
        Initialize wallet sync manager

        Args:
            tolerance_percentage: Acceptable difference % before triggering sync
        """
        self.tolerance_percentage = tolerance_percentage
        self.last_sync_timestamp = None
        self.sync_history = []

    def check_wallet_sync(
        self,
        agent_state: Dict[str, Any],
        actual_wallet_balance: float
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Check if agent state matches actual wallet balance

        Args:
            agent_state: Current agent state
            actual_wallet_balance: Actual SOL balance from blockchain

        Returns:
            Tuple of (is_synced, message, suggested_adjustments)
        """
        try:
            # Get agent's believed balance
            agent_balance = agent_state.get('wallet_balance_sol', 0)

            # Calculate difference
            difference = actual_wallet_balance - agent_balance
            difference_percentage = (abs(difference) / agent_balance * 100) if agent_balance > 0 else 100

            # Check if within tolerance
            is_synced = difference_percentage <= self.tolerance_percentage

            if is_synced:
                return True, f"✅ Wallet synced (diff: {difference_percentage:.2f}%)", None

            # Wallet out of sync - determine reason
            if difference > 0:
                # External deposit detected
                message = f"💰 External deposit detected: +{difference:.4f} SOL (+{difference_percentage:.1f}%)"
                sync_type = "deposit"
            else:
                # External withdrawal detected
                message = f"⚠️ External withdrawal detected: {difference:.4f} SOL (-{difference_percentage:.1f}%)"
                sync_type = "withdrawal"

            # Calculate suggested adjustments
            adjustments = self._calculate_adjustments(
                agent_state,
                agent_balance,
                actual_wallet_balance,
                difference,
                sync_type
            )

            # Log the discrepancy
            self._log_sync_event(
                agent_balance=agent_balance,
                actual_balance=actual_wallet_balance,
                difference=difference,
                sync_type=sync_type
            )

            return False, message, adjustments

        except Exception as e:
            logger.error(f"Error checking wallet sync: {e}")
            return False, f"❌ Sync check failed: {e}", None

    def _calculate_adjustments(
        self,
        agent_state: Dict[str, Any],
        old_balance: float,
        new_balance: float,
        difference: float,
        sync_type: str
    ) -> Dict[str, Any]:
        """
        Calculate necessary adjustments to agent state

        Args:
            agent_state: Current agent state
            old_balance: Agent's believed balance
            new_balance: Actual wallet balance
            difference: Balance difference
            sync_type: 'deposit' or 'withdrawal'

        Returns:
            Dict with suggested adjustments
        """
        try:
            active_positions = agent_state.get('active_positions', [])

            # Calculate total capital in positions
            capital_in_positions = sum(
                pos.get('amount_sol', 0) for pos in active_positions
            )

            # Calculate available capital
            old_available = old_balance - capital_in_positions
            new_available = new_balance - capital_in_positions

            adjustments = {
                'old_balance': old_balance,
                'new_balance': new_balance,
                'difference': difference,
                'sync_type': sync_type,
                'capital_in_positions': capital_in_positions,
                'old_available_capital': old_available,
                'new_available_capital': new_available,
                'active_positions_count': len(active_positions),
                'timestamp': datetime.now().isoformat()
            }

            # Check if positions are affected
            if sync_type == 'withdrawal':
                # Check if withdrawal affects position management
                if new_available < 0:
                    adjustments['warning'] = "⚠️ CRITICAL: Negative available capital! Positions may need closing."
                    adjustments['suggested_action'] = "close_positions"
                    adjustments['positions_to_close'] = self._suggest_positions_to_close(
                        active_positions,
                        abs(new_available)
                    )
                elif new_available < old_available * 0.5:
                    adjustments['warning'] = "⚠️ Available capital reduced by 50%+. Consider reducing position sizes."
                    adjustments['suggested_action'] = "reduce_positions"
                else:
                    adjustments['warning'] = "ℹ️ Withdrawal detected. Future trades will use lower capital."
                    adjustments['suggested_action'] = "adjust_parameters"

            elif sync_type == 'deposit':
                # Deposit detected
                adjustments['info'] = f"💰 +{difference:.4f} SOL available for trading"
                adjustments['suggested_action'] = "increase_capacity"

            # Calculate new risk parameters
            if agent_state.get('agent_parameters'):
                params = agent_state['agent_parameters']
                old_risk_per_trade = old_balance * params.get('risk_per_trade_percentage', 5) / 100
                new_risk_per_trade = new_balance * params.get('risk_per_trade_percentage', 5) / 100

                adjustments['old_risk_per_trade'] = old_risk_per_trade
                adjustments['new_risk_per_trade'] = new_risk_per_trade
                adjustments['risk_change'] = new_risk_per_trade - old_risk_per_trade

            return adjustments

        except Exception as e:
            logger.error(f"Error calculating adjustments: {e}")
            return {'error': str(e)}

    def _suggest_positions_to_close(
        self,
        positions: list,
        amount_needed: float
    ) -> list:
        """
        Suggest which positions to close to free up capital

        Args:
            positions: List of active positions
            amount_needed: Amount of SOL needed

        Returns:
            List of position indices to close
        """
        try:
            # Sort positions by unrealized PnL (close losers first, then winners)
            sorted_positions = sorted(
                enumerate(positions),
                key=lambda x: self._calculate_position_pnl(x[1])
            )

            to_close = []
            freed_capital = 0

            for idx, pos in sorted_positions:
                if freed_capital >= amount_needed:
                    break

                to_close.append({
                    'index': idx,
                    'symbol': pos.get('token_symbol', 'Unknown'),
                    'amount_sol': pos.get('amount_sol', 0),
                    'unrealized_pnl': self._calculate_position_pnl(pos)
                })

                freed_capital += pos.get('amount_sol', 0)

            return to_close

        except Exception as e:
            logger.error(f"Error suggesting positions to close: {e}")
            return []

    def _calculate_position_pnl(self, position: Dict[str, Any]) -> float:
        """Calculate unrealized PnL for a position"""
        try:
            entry_price = position.get('entry_price_usd', 0)
            current_price = position.get('current_price_usd', entry_price)

            if entry_price == 0:
                return 0

            return ((current_price - entry_price) / entry_price) * 100
        except:
            return 0

    def sync_agent_state(
        self,
        agent_state: Dict[str, Any],
        actual_balance: float,
        adjustments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sync agent state with actual wallet balance AND adjust PnL tracking

        Args:
            agent_state: Current agent state
            actual_balance: Actual wallet balance
            adjustments: Calculated adjustments

        Returns:
            Updated agent state with corrected PnL tracking
        """
        try:
            difference = adjustments.get('difference', 0)
            sync_type = adjustments.get('sync_type', 'unknown')

            # Initialize external cash flows tracking if not exists
            if 'external_cash_flows' not in agent_state:
                agent_state['external_cash_flows'] = []

            # Record this external cash flow
            cash_flow_entry = {
                'timestamp': datetime.now().isoformat(),
                'amount_sol': difference,
                'type': sync_type,  # 'deposit' or 'withdrawal'
                'balance_before': adjustments.get('old_balance', 0),
                'balance_after': actual_balance
            }
            agent_state['external_cash_flows'].append(cash_flow_entry)

            # Update cumulative external cash flows
            if 'total_external_deposits' not in agent_state:
                agent_state['total_external_deposits'] = 0
            if 'total_external_withdrawals' not in agent_state:
                agent_state['total_external_withdrawals'] = 0

            if sync_type == 'deposit':
                agent_state['total_external_deposits'] += abs(difference)
            elif sync_type == 'withdrawal':
                agent_state['total_external_withdrawals'] += abs(difference)

            # Update balance
            old_balance = agent_state.get('wallet_balance_sol', 0)
            agent_state['wallet_balance_sol'] = actual_balance

            # CRITICAL: Adjust starting capital for PnL calculation
            # This ensures PnL is calculated ONLY on trading performance
            if 'adjusted_starting_capital' not in agent_state:
                agent_state['adjusted_starting_capital'] = old_balance

            # Adjust starting capital by external flows
            # Withdrawals INCREASE starting capital (for PnL purposes)
            # Deposits DECREASE starting capital (for PnL purposes)
            if sync_type == 'withdrawal':
                # If you withdrew 50 SOL, that 50 shouldn't count as "loss"
                agent_state['adjusted_starting_capital'] -= difference  # difference is negative
            elif sync_type == 'deposit':
                # If you deposited 50 SOL, that 50 shouldn't count as "gain"
                agent_state['adjusted_starting_capital'] -= difference  # difference is positive

            # Calculate TRUE trading PnL (excluding external flows)
            true_trading_pnl = self._calculate_true_trading_pnl(agent_state)
            agent_state['true_trading_pnl'] = true_trading_pnl

            # Add sync metadata
            agent_state['last_wallet_sync'] = datetime.now().isoformat()
            agent_state['wallet_sync_adjustments'] = adjustments

            # Add warning if critical
            if adjustments.get('warning'):
                agent_state['wallet_sync_warning'] = adjustments['warning']

            # Add PnL adjustment notice
            pnl_notice = self._generate_pnl_notice(
                sync_type,
                difference,
                true_trading_pnl
            )
            if pnl_notice:
                agent_state['pnl_adjustment_notice'] = pnl_notice

            # Log sync with PnL info
            logger.info(
                f"Wallet synced: {old_balance:.4f} → {actual_balance:.4f} SOL | "
                f"External {sync_type}: {abs(difference):.4f} SOL | "
                f"True Trading PnL: {true_trading_pnl.get('pnl_sol', 0):.4f} SOL "
                f"({true_trading_pnl.get('pnl_percentage', 0):.2f}%)"
            )

            self.last_sync_timestamp = datetime.now()

            return agent_state

        except Exception as e:
            logger.error(f"Error syncing agent state: {e}")
            return agent_state

    def _calculate_true_trading_pnl(self, agent_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate TRUE trading PnL excluding external deposits/withdrawals

        Formula (from research):
        True PnL = Current Assets - Starting Capital - Net Deposits + Net Withdrawals

        Args:
            agent_state: Current agent state

        Returns:
            Dict with PnL metrics
        """
        try:
            current_balance = agent_state.get('wallet_balance_sol', 0)
            active_positions = agent_state.get('active_positions', [])

            # Calculate total current assets (cash + positions)
            position_value = sum(
                pos.get('current_value_sol', 0) for pos in active_positions
            )
            total_current_assets = current_balance + position_value

            # Get adjusted starting capital (accounts for external flows)
            adjusted_starting = agent_state.get(
                'adjusted_starting_capital',
                agent_state.get('initial_wallet_balance_sol', 100)
            )

            # Calculate true trading PnL
            true_pnl_sol = total_current_assets - adjusted_starting
            true_pnl_percentage = (true_pnl_sol / adjusted_starting * 100) if adjusted_starting > 0 else 0

            # Also track without adjustment for comparison
            naive_starting = agent_state.get('initial_wallet_balance_sol', 100)
            naive_pnl_sol = total_current_assets - naive_starting
            naive_pnl_percentage = (naive_pnl_sol / naive_starting * 100) if naive_starting > 0 else 0

            return {
                'total_current_assets': total_current_assets,
                'adjusted_starting_capital': adjusted_starting,
                'pnl_sol': true_pnl_sol,
                'pnl_percentage': true_pnl_percentage,
                'naive_pnl_sol': naive_pnl_sol,
                'naive_pnl_percentage': naive_pnl_percentage,
                'pnl_difference': true_pnl_sol - naive_pnl_sol,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error calculating true PnL: {e}")
            return {
                'pnl_sol': 0,
                'pnl_percentage': 0,
                'error': str(e)
            }

    def _generate_pnl_notice(
        self,
        sync_type: str,
        difference: float,
        true_pnl: Dict[str, Any]
    ) -> str:
        """Generate a notice about PnL adjustment"""
        try:
            pnl_diff = true_pnl.get('pnl_difference', 0)

            if abs(pnl_diff) < 0.01:
                return None

            if sync_type == 'withdrawal':
                return (
                    f"📊 PnL Adjusted: Your {abs(difference):.4f} SOL withdrawal "
                    f"excluded from performance calculation. "
                    f"True trading PnL: {true_pnl.get('pnl_percentage', 0):.2f}%"
                )
            elif sync_type == 'deposit':
                return (
                    f"📊 PnL Adjusted: Your {abs(difference):.4f} SOL deposit "
                    f"excluded from performance calculation. "
                    f"True trading PnL: {true_pnl.get('pnl_percentage', 0):.2f}%"
                )

            return None

        except:
            return None

    def _log_sync_event(
        self,
        agent_balance: float,
        actual_balance: float,
        difference: float,
        sync_type: str
    ):
        """Log wallet sync event"""
        try:
            event = {
                'timestamp': datetime.now().isoformat(),
                'agent_balance': agent_balance,
                'actual_balance': actual_balance,
                'difference': difference,
                'sync_type': sync_type
            }

            self.sync_history.append(event)

            # Keep only last 100 events
            if len(self.sync_history) > 100:
                self.sync_history = self.sync_history[-100:]

            logger.warning(f"WALLET SYNC EVENT: {sync_type.upper()} - Difference: {difference:.4f} SOL")

        except Exception as e:
            logger.error(f"Error logging sync event: {e}")

    def get_sync_report(self) -> Dict[str, Any]:
        """Get a report of recent sync events"""
        try:
            return {
                'last_sync': self.last_sync_timestamp.isoformat() if self.last_sync_timestamp else None,
                'total_events': len(self.sync_history),
                'recent_events': self.sync_history[-10:] if self.sync_history else [],
                'tolerance_percentage': self.tolerance_percentage
            }
        except Exception as e:
            logger.error(f"Error generating sync report: {e}")
            return {'error': str(e)}


# Global wallet sync manager instance
_global_sync_manager = None


def get_wallet_sync_manager() -> WalletSyncManager:
    """Get or create global wallet sync manager"""
    global _global_sync_manager
    if _global_sync_manager is None:
        _global_sync_manager = WalletSyncManager()
    return _global_sync_manager


def check_and_sync_wallet(
    agent_state: Dict[str, Any],
    actual_balance: float,
    auto_sync: bool = True
) -> Tuple[Dict[str, Any], bool, str]:
    """
    Convenience function to check and optionally sync wallet

    Args:
        agent_state: Current agent state
        actual_balance: Actual wallet balance from blockchain
        auto_sync: Whether to auto-sync if out of sync

    Returns:
        Tuple of (updated_state, was_synced, message)
    """
    try:
        sync_manager = get_wallet_sync_manager()

        # Check sync
        is_synced, message, adjustments = sync_manager.check_wallet_sync(
            agent_state,
            actual_balance
        )

        if is_synced:
            return agent_state, True, message

        # Out of sync
        logger.warning(f"Wallet out of sync: {message}")

        if auto_sync:
            # Sync agent state
            updated_state = sync_manager.sync_agent_state(
                agent_state,
                actual_balance,
                adjustments
            )

            sync_message = f"{message}\n🔄 Agent state synchronized"
            return updated_state, True, sync_message
        else:
            # Return with warning but don't sync
            return agent_state, False, message

    except Exception as e:
        logger.error(f"Error in check_and_sync_wallet: {e}")
        return agent_state, False, f"❌ Sync failed: {e}"
