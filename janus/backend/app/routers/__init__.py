# Routers do JUNO Backend.
#
# IMPORTANTE: NAO importar routers automaticamente aqui -- fazer import lazy
# nos lugares que precisarem (ex.: app/main.py). Importar tudo de uma vez
# faz com que dependencias pesadas (mlflow, openai, etc.) sejam carregadas
# mesmo quando o router nao vai ser registrado no app, o que quebra setup
# de testes e build do CI.
