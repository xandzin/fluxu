# Guia de implantação — Sistema de Conveniência

Este guia é pra instalar o sistema num PC novo (o PC da loja) e deixá-lo
rodando de forma confiável no dia a dia.

## 0. O que copiar pro PC novo

Copie a pasta `sistema-conveniencia` inteira (USB, e-mail, OneDrive, como for
mais fácil) para o PC da loja, em `C:\sistema-conveniencia` ou onde preferir.

Arquivos importantes que devem estar dentro:

- `app.py`, `schema.sql`, `templates\`, `static\` — o sistema em si
- `estoque.db` — **o banco já vem com os 915 produtos do catálogo Petro
  cadastrados, e vendas/compras/caixa zerados** (pronto pra começar do zero
  hoje). **Sem senha definida ainda** — o primeiro acesso vai pedir pra
  criar a senha do sistema (ver passo 6).
- `registrar_venda.py` — versão de terminal (alternativa se o navegador
  falhar por algum motivo)
- `importar_complemento.py` — pra acrescentar categorias novas do Petro no
  futuro (seguro, só adiciona, nunca apaga)
- `backup_diario.py` — script de backup (configurar no passo 5)
- `iniciar_servidor.bat` — atalho pra ligar o sistema

Não precisa copiar `secret_key.txt` se ele existir aqui — é gerado
automaticamente na primeira vez que o sistema roda no PC novo. Se você
copiar o arquivo antigo por engano, também não tem problema.

**Não precisa se preocupar com `import_dados.py`** — ele é uma ferramenta de
migração de quando o catálogo foi montado, já tem um aviso grande escrito nele
pra não ser usado por engano, e nem funcionaria no PC novo (depende de
planilhas que só existem no PC de desenvolvimento).

## 1. Instalar o Python no PC novo

1. Baixe o instalador em **python.org/downloads** (versão 3.11 ou mais
   recente).
2. Ao instalar, **marque a caixa "Add python.exe to PATH"** na primeira tela
   do instalador — isso é fácil de esquecer e causa dor de cabeça depois.
3. Abra um **novo** PowerShell ou Prompt de Comando e teste:
   ```
   python --version
   ```
   Deve mostrar algo como `Python 3.12.x`.

   **Se aparecer uma mensagem dizendo que o Python não foi encontrado e
   oferecendo abrir a Microsoft Store** (isso aconteceu no PC de
   desenvolvimento): vá em *Configurações do Windows → Aplicativos →
   Configurações avançadas de aplicativos → Aliases de execução de app* e
   desligue o alias do `python.exe`/`python3.exe`. Teste `python --version`
   de novo depois.

4. Instale o Flask (única dependência externa):
   ```
   pip install flask
   ```

## 2. Testar localmente no PC novo

1. Dê duplo clique em `iniciar_servidor.bat`.
2. Deve aparecer uma janela preta dizendo que o servidor está rodando.
3. Abra o navegador **nesse mesmo PC** em `http://localhost:5000` — deve
   abrir a tela de Venda.
4. Se não abrir, a janela preta vai mostrar o erro. Os erros mais comuns:
   - Python não instalado/não no PATH → volte ao passo 1.
   - Flask não instalado → rode `pip install flask` de novo.

## 3. Liberar o acesso pela rede (pra outros PCs/caixas acessarem)

Mesmos passos que já usamos no PC de desenvolvimento:

1. **Confira o perfil de rede.** Rode no PowerShell:
   ```
   Get-NetConnectionProfile
   ```
   Se aparecer `Public`, o Firewall do Windows vai bloquear outros PCs por
   padrão. Duas opções (escolha uma):
   - Marcar a rede como **Privada** em Configurações → Rede e Internet.
   - Ou criar uma regra de firewall só pra porta 5000 (PowerShell **como
     Administrador**):
     ```
     New-NetFirewallRule -DisplayName "Sistema Conveniencia (porta 5000)" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Any
     ```

2. **Descubra o IP do PC servidor** na rede da loja:
   ```
   ipconfig
   ```
   Procure o "Endereço IPv4" do adaptador Wi-Fi ou Ethernet ativo (algo tipo
   `192.168.X.X`).

3. Nos outros PCs/caixas, abra o navegador em `http://IP-DO-SERVIDOR:5000` e
   favorite essa página.

   **Atenção:** esse IP pode mudar se o roteador reatribuir endereço (depois
   de reiniciar o PC ou o roteador). Se isso for um problema no dia a dia,
   configure um IP fixo pro PC servidor nas propriedades do adaptador de
   rede, ou reserve o IP dele no roteador (menu DHCP do roteador).

## 4. Auto-iniciar quando o PC ligar

Pra o sistema voltar sozinho se o PC reiniciar (queda de energia, atualização
do Windows, etc):

1. Aperte `Win + R`, digite `shell:startup` e Enter — abre a pasta de
   Inicialização do Windows.
2. Copie um **atalho** de `iniciar_servidor.bat` pra dentro dessa pasta
   (botão direito no `.bat` → Criar atalho → arraste o atalho pra essa
   pasta).
3. Reinicie o PC uma vez pra confirmar que a janela do servidor abre
   sozinha.

**Importante pra quem for usar o PC no dia a dia:** essa janela preta que
abre precisa ficar aberta (pode minimizar) enquanto o sistema estiver em
uso. Fechar a janela ou apertar Ctrl+C nela desliga o sistema pra todo mundo.

## 5. Backup automático

`backup_diario.py` copia o banco pra pasta `backups\` (mantém os últimos 30
dias sozinho). Agende ele pra rodar todo dia:

1. Abra o **Agendador de Tarefas** do Windows (pesquise no menu iniciar).
2. **Criar Tarefa Básica** → nome "Backup Sistema Conveniência".
3. Disparador: **Diariamente**, horário de sua preferência (ex: 23:55, ou de
   manhã bem cedo antes de abrir).
4. Ação: **Iniciar um programa**.
   - Programa/script: caminho completo do `python.exe` (o mesmo que você
     testou no passo 1 — geralmente algo como
     `C:\Users\SEUUSUARIO\AppData\Local\Programs\Python\Python312\python.exe`,
     confirme com `where.exe python`).
   - Argumentos: caminho completo do `backup_diario.py`, entre aspas.
   - Iniciar em: a pasta `sistema-conveniencia`.
5. Salve e rode a tarefa manualmente uma vez (botão direito → Executar) pra
   confirmar que criou um arquivo em `backups\`.

**Recomendado:** de vez em quando, copie a pasta `backups\` pra um pendrive
ou pasta do OneDrive/Google Drive. Backup que mora só no mesmo PC do sistema
não protege contra o PC quebrar, ser roubado, etc.

## 6. Definir a senha do sistema

O sistema inteiro pede login (senha única, compartilhada pela equipe). Na
primeira vez que alguém abrir o sistema nesse PC, em vez de pedir a senha ele
vai pedir pra **definir** uma — é só digitar a senha desejada duas vezes.
Depois disso, todo mundo usa essa mesma senha pra entrar.

Pra trocar a senha depois, é em **Dashboard → Trocar senha do sistema**
(precisa saber a senha atual).

## 7. Antes de abrir pro pessoal usar — checklist final

- [ ] **Data e hora do Windows estão certas** (Configurações → Hora e
      Idioma). O sistema grava a data da venda automaticamente a partir do
      relógio do PC — se estiver errado, toda venda do dia fica com data
      errada.
- [ ] Definiu a senha do sistema (passo 6).
- [ ] Testou registrar uma venda de ponta a ponta neste PC — **lembrando
      que precisa abrir o caixa primeiro** (tela Caixa) antes da tela de
      Venda liberar.
- [ ] Testou acessar de outro PC/caixa pela rede.
- [ ] Testou o backup manualmente (passo 5).
- [ ] Reiniciou o PC pra confirmar que o auto-início funciona.
- [ ] Equipe sabe onde fica o atalho/endereço pra abrir o sistema, a senha,
      e como abrir/fechar caixa (ver `GUIA_OPERADOR.md`).

## 8. Atualizações futuras (via Git)

O código do sistema agora vive num repositório Git. Isso separa **código**
(o que muda quando eu implemento algo novo) de **dados de produção**
(`estoque.db`, `secret_key.txt`, `backups\`) — essas três coisas estão no
`.gitignore` e nunca são tocadas por uma atualização.

### Instalação inicial no PC da loja (uma vez só)

1. Instale o Git no PC da loja (mesmo processo do Python: baixe em
   [git-scm.com](https://git-scm.com/downloads), instale com as opções
   padrão).
2. No lugar de copiar a pasta manualmente, clone o repositório:
   ```
   git clone <URL-do-repositorio> C:\sistema-conveniencia
   ```
3. Como o `estoque.db` e o `secret_key.txt` não vêm no repositório (de
   propósito), na primeira vez que rodar `iniciar_servidor.bat` o sistema
   cria um banco novo vazio (só a estrutura, sem produtos) e vai pedir pra
   definir a senha. **Nesse caso**, ainda é preciso copiar o `estoque.db`
   real (com os 915 produtos) por USB/rede separadamente, uma vez, por cima
   do banco vazio que foi criado — depois disso o Git nunca mais encosta
   nele.

### Lançando uma atualização (toda vez que eu mudar algo)

No PC de desenvolvimento, depois de qualquer mudança, o código é commitado e
enviado (`git push`) pro repositório remoto.

No PC da loja, pra buscar a atualização:

1. Feche o sistema (feche a janela preta do `iniciar_servidor.bat`, ou pare
   o processo).
2. Abra um terminal na pasta `C:\sistema-conveniencia` e rode:
   ```
   git pull
   ```
   Isso baixa e aplica só os arquivos de código que mudaram — o
   `estoque.db` fica intocado porque está fora do controle do Git.
3. Se alguma mudança precisar de uma biblioteca nova, rode `pip install
   flask` de novo (eu aviso quando isso for necessário).
4. Abra o `iniciar_servidor.bat` de novo. Se a atualização mudou a estrutura
   do banco (uma tabela ou coluna nova), o próprio sistema ajusta isso
   sozinho na hora que liga, sem apagar nada — é a mesma lógica segura que já usamos até aqui.

**Antes de qualquer atualização importante, vale rodar `backup_diario.py`
manualmente** (ou copiar `estoque.db` pra um lugar seguro) — é raro dar
problema, mas é grátis se garantir.

**Recomendado:** peça pra eu te passar um `atualizar.bat` simples que faz o
`git pull` com um clique, quando for usar isso no dia a dia — assim ninguém
precisa abrir terminal na loja.

## Limitações que você decidiu aceitar por enquanto (revisitar quando fizer
## sentido)

- **Uma senha só, compartilhada por todo mundo.** Não dá pra saber qual
  funcionário fez qual venda ou correção — se isso passar a importar (ex.:
  equipe cresceu, precisa apurar responsabilidade por um erro), o próximo
  passo seria contas individuais por funcionário.
- **Acesso só na rede local da loja.** Ver os relatórios de fora da loja
  (do celular, de casa) não está configurado — isso exigiria expor o
  sistema pra internet de forma segura, um projeto à parte, não incluído aqui.
- **Um único PC guarda o banco.** Se esse PC quebrar sem backup em dia,
  perde-se o histórico desde o último backup. Por isso o passo 5 não é
  opcional.
