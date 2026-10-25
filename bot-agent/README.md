lk agent console --text bot-agent/src/bot_agent/agent.py


cd bot-agent/
lk agent create
lk agent update
lk agent console --text
lk agent dev src/bot_agent/agent.py 
uv run bot-agent console
lk room join --room test-1 --identity me --publish
uv run bot-agent console

lk agent console
lk agent dev
lk agent debugger start
lk agent debugger say "Hi, what can you do?"
lk agent debugger say "qual è la radice quadrata di 49?"
lk agent debugger say "fai un esempio semplice di equazione il cui risultato è una funzione"
lk agent debugger stop
lk agent console
lk agent create
lk agent console
lk agent console --text

