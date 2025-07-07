(env) harry@DESKTOP-V47OS7O:~/projects/DevThukuDotIO/SnowballResearch/lambda-trading-bot$ python -c "from src.agent import run_trading_agent; print('✅ Basic import works')"
 -c "from src.agent.langgraph_trading_agent import run_langgraph_trading_cycle; print('✅ LangGraph import works')"
Social Intelligence client initialized without TweetScout API key
✅ Basic import works
(env) harry@DESKTOP-V47OS7O:~/projects/DevThukuDotIO/SnowballResearch/lambda-trading-bot$ python -c "from src.agent.langgraph_trading_agent import run_langgraph_trading_cycle; print('✅ LangGraph import works')"
Social Intelligence client initialized without TweetScout API key
✅ LangGraph import works
(env) harry@DESKTOP-V47OS7O:~/projects/DevThukuDotIO/SnowballResearch/lambda-trading-bot$ python -c "
> from src.agent import run_trading_agent
> result = run_trading_agent()
> print(f'Cycles: {result.get(\"cycles_completed\", 0)}')
> print(f'Tools used: {result.get(\"tools_used_this_cycle\", [])}')
> print(f'State healthy: {result.get(\"state_healthy\", False)}')
> "
Social Intelligence client initialized without TweetScout API key
❌ Complete LangGraph trading cycle error: Error code: 429 - {'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'This request would exceed the rate limit for your organization (59c771cd-9c34-4a8c-a0ea-f1e4127a79a6) of 40,000 input tokens per minute. For details, refer to: https://docs.anthropic.com/en/api/rate-limits. You can see the response headers for current usage. Please reduce the prompt length or the maximum tokens requested, or try again later. You may also contact sales at https://www.anthropic.com/contact-sales to discuss your options for a rate limit increase.'}}
⚠️ LangGraph cycle 101 completed but no tools were used
Cycles: 101
Tools used: []
State healthy: True
(env) harry@DESKTOP-V47OS7O:~/projects/DevThukuDotIO/SnowballResearch/lambda-trading-bot$