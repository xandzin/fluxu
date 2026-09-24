# Fluxu — Sistema de Gestão para Conveniência

Sistema completo de gestão desenvolvido para conveniência de posto de gasolina, atualmente em produção no comércio da família.

## Sobre o projeto

O Fluxu nasceu da necessidade real de substituir o controle em planilhas por um sistema próprio, adaptado ao dia a dia de uma conveniência: cadastro de produtos, controle de estoque, registro de vendas, fechamento de caixa e relatórios operacionais.

Foi desenvolvido do zero — do levantamento de requisitos junto ao operador ao deploy no ambiente da loja, incluindo rotina de backup diário e scripts de inicialização e atualização para uso por pessoas não-técnicas.

## Stack

- **Backend:** Python 3 + Flask
- **Banco de dados:** SQLite
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **Deploy:** Servidor local com scripts `.bat` para inicialização e atualização
- **Backup:** Rotina automatizada em Python

## Funcionalidades

- Cadastro e gestão de produtos
- Controle de estoque com histórico
- Registro de vendas
- Fechamento e conferência de caixa
- Importação de dados via CSV
- Backup diário automatizado

## Estrutura

- `app.py` — aplicação Flask principal
- `schema.sql` — esquema do banco
- `templates/` — páginas HTML (Jinja2)
- `static/` — CSS, JS e assets
- `backup_diario.py` — rotina de backup
- `import_dados.py` — importação em lote
- `GUIA_IMPLANTACAO.md` — guia de implantação em novo ambiente
- `GUIA_OPERADOR.md` — manual do operador

## Status

Em produção desde julho/2026.

## Autor

Alexandre Soares — [LinkedIn](https://www.linkedin.com/in/alexandre-soares-b29358248/)