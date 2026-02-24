# Sistema Delivery – Flask + MySQL

## Aplicação web de delivery desenvolvida com Python (Flask) e MySQL, permitindo:

- Cadastro de clientes e restaurantes
- Login com autenticação segura (hash de senha)
- Cadastro e edição de cardápio
- Carrinho de compras, com remoção a adição do item do cardápio
- Finalização de pedidos
- Gestão de pedidos pelo restaurante
  
## Tecnologias Utilizadas

- Python 3
- Flask
- MySQL
- mysql-connector-python
- Jinja2
- HTML + CSS
- Ambiente virtual (venv)

# Como Rodar o Projeto

## Pré-requisitos
- Python 3.10 ou superior
- MySQL Server 8.0 ou superior
- Git
## Clonar o Repositório

``` 
git clone https://github.com/luanalauschner/Delivery.git
cd Delivery
```
## Criar e ativar ambiente virtual

### No Windows
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
### No Mac/Linux
```
python3 -m venv .venv
source .venv/bin/activate
```

## Instalar dependências

```
pip install -r requirements.txt
```

## Configurar variáveis de ambiente

### No Windows
```
copy .env.example .env
```
### No Mac/Linux
```
cp .env.example .env
```
### No arquivo .env ajuste a senha do MySQL
#### Se o MySQL não tiver senha, MYSQL_PASSWORD= vazio

```
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=sua_senha_aqui
MYSQL_DB=sistema_delivery_db
MYSQL_PORT=3306
FLASK_SECRET_KEY=dev-secret
```
## Criar o Banco de Dados  

```
mysql -u root -p -e "DROP DATABASE IF EXISTS sistema_delivery_db; CREATE DATABASE sistema_delivery_db;"
```

### Carregue as tabelas e os dados inciais
#### Windows (PowerShell)
```
Get-Content .\schema.sql | mysql -u root -p sistema_delivery_db
Get-Content .\seed.sql   | mysql -u root -p sistema_delivery_db
```
#### Mac/Linux (ou Windows CMD)
```
mysql -u root -p sistema_delivery_db < schema.sql
mysql -u root -p sistema_delivery_db < seed.sql
```

## Rodar o servidor 

### Com o ambiente virtual ativo:

```
python app.py
```
## O link que aparecerá será:

```
http://127.0.0.1:5000
```

# Como Utilizar o Sistema

## Cliente
- Acesse "Cadastro"

- Crie uma conta como CLIENTE

- Faça login

- Escolha um restaurante

- Adicione itens ao carrinho

- Finalize pedido

- Acompanhe em "Meus Pedidos"

## Restaurante
- Acesse "Cadastro"

- Crie uma conta como RESTAURANTE

- Faça login
- Acompanho e altere status dos pedidos em "Ver Pedidos"
- Alterar Cardápio em "Gerenciar Cardápio"
- Para entrar nos restaurante já cadastrados:

  NoBalde:
    NoBalde@gmail.com
  
  Barollo:
    barollo@gmail.com
  
  Amozônico:
    amazonico@gmail.com
  
    senha: 123

# Estrutura do Projeto
```
Delivery/
│
├── app.py                # Rotas e lógica principal
├── db.py                 # Conexão com banco de dados
├── schema.sql            # Estrutura do banco
├── seed.sql              # Dados iniciais
├── requirements.txt      # Dependências
├── .env.example          # Modelo de configuração
├── MER_DER               # MER e DER do projeto
└── templates/            # Páginas HTML
```
