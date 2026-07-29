@echo off
cd /d "%~dp0"
echo Iniciando o sistema de conveniencia...
echo Deixe esta janela aberta e minimizada (nao feche) enquanto o sistema estiver em uso.
echo.
python app.py
if errorlevel 1 (
    echo.
    echo ============================================================
    echo O servidor parou ou nao iniciou. Verifique se o Python esta
    echo instalado e adicionado ao PATH (veja GUIA_IMPLANTACAO.md).
    echo ============================================================
)
pause
