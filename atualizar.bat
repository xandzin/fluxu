@echo off
title Sistema Conveniencia - Atualizando
cd /d "%~dp0"

echo ============================================================
echo Atualizando o sistema de conveniencia...
echo ============================================================
echo.

git pull
if errorlevel 1 (
    echo.
    echo ============================================================
    echo A atualizacao falhou. Motivos comuns:
    echo  - Sem conexao com a internet.
    echo  - Git nao instalado (veja GUIA_IMPLANTACAO.md, secao 8).
    echo O sistema antigo continua funcionando normalmente.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo Verificando dependencias...
pip install -r requirements.txt -q

echo.
echo Fechando o servidor antigo, se estiver aberto...
taskkill /FI "WINDOWTITLE eq Sistema Conveniencia - Servidor*" /T /F >nul 2>&1

echo.
echo ============================================================
echo Atualizacao concluida! Iniciando o sistema com a versao nova...
echo ============================================================
timeout /t 2 >nul
start "" "iniciar_servidor.bat"

echo.
echo Pode fechar esta janela.
pause
