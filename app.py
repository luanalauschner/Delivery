from flask import Flask, render_template, abort, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db

app = Flask(__name__)
app.secret_key = "dev-secret"  # depois coloque isso no .env

# =========================
# Helpers de autenticação
# =========================
def get_usuario_logado():
    """
    Retorna {"id": <int>, "tipo": "CLIENTE"|"RESTAURANTE"} ou None.
    """
    uid = session.get("usuario_id")
    tipo = session.get("tipo")
    if not uid or not tipo:
        return None
    return {"id": uid, "tipo": tipo}


def exigir_login(tipo_necessario=None):
    """
    Se não estiver logado: redireciona para /login?next=<rota atual>
    Se tipo_necessario for informado e não bater: retorna 403.
    Se tudo OK: retorna None.
    """
    user = get_usuario_logado()
    if not user:
        return redirect(url_for("login_form", next=request.path))

    if tipo_necessario and user["tipo"] != tipo_necessario:
        return "Acesso negado: tipo de usuário inválido.", 403

    return None
# =========================
# Home / Cardápio público
# =========================
@app.get("/")
def home():
    user = get_usuario_logado()

    # Se for RESTAURANTE, não mostra home de cliente
    if user and user["tipo"] == "RESTAURANTE":
        return redirect(url_for("restaurante_home"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT usuario_id, nome, status, tempo_preparo_min, tempo_preparo_max
        FROM restaurantes
        WHERE status='ABERTO'
        ORDER BY nome
    """)
    restaurantes = cur.fetchall() #retorna tudo

    cur.close() #fecha cursor
    db.close() #fecha o banco
    return render_template("home.html", restaurantes=restaurantes, user=user)

@app.get("/restaurantes/<int:rid>")
def ver_restaurante(rid):
    user = get_usuario_logado()
    if user and user["tipo"] == "RESTAURANTE":
        return redirect(url_for("restaurante_home"))
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT usuario_id, nome, status FROM restaurantes WHERE usuario_id=%s", (rid,))
    rest = cur.fetchone()
    if not rest:
        cur.close()
        db.close()
        abort(404)

    cur.execute("""
        SELECT id, nome, descricao, preco_base
        FROM itens_cardapio
        WHERE restaurante_id=%s AND disponivel=1
        ORDER BY nome
    """, (rid,))
    itens = cur.fetchall()

    cur.close()
    db.close()

    return render_template("restaurante.html", restaurante=rest, itens=itens, user=get_usuario_logado())


# =========================
# Carrinho
# =========================
@app.post("/carrinho/add")
def carrinho_add():
    item_id = int(request.form["item_id"])
    restaurante_id = int(request.form["restaurante_id"])

    carrinho = session.get("carrinho", {})
    carrinho_rest = session.get("carrinho_restaurante_id")

    # Um carrinho só pode ter itens de 1 restaurante
    if carrinho_rest and carrinho_rest != restaurante_id:
        carrinho = {}

    session["carrinho_restaurante_id"] = restaurante_id
    carrinho[str(item_id)] = carrinho.get(str(item_id), 0) + 1
    session["carrinho"] = carrinho

    return redirect(url_for("ver_restaurante", rid=restaurante_id))


@app.post("/carrinho/remove")
def carrinho_remove():
    item_id = request.form["item_id"]
    carrinho = session.get("carrinho", {})

    if item_id in carrinho:
        del carrinho[item_id]

    if not carrinho:
        session.pop("carrinho_restaurante_id", None)

    session["carrinho"] = carrinho
    return redirect(url_for("ver_carrinho"))


@app.post("/carrinho/decrease")
def carrinho_decrease():
    item_id = request.form["item_id"]
    carrinho = session.get("carrinho", {})

    if item_id in carrinho:
        if carrinho[item_id] <= 1:
            del carrinho[item_id]
        else:
            carrinho[item_id] -= 1

    if not carrinho:
        session.pop("carrinho_restaurante_id", None)

    session["carrinho"] = carrinho
    return redirect(url_for("ver_carrinho"))


@app.get("/carrinho")
def ver_carrinho():
    carrinho = session.get("carrinho", {})
    restaurante_id = session.get("carrinho_restaurante_id")

    if not carrinho or not restaurante_id:
        return render_template(
            "carrinho.html",
            itens=[],
            subtotal=0,
            restaurante_id=None,
            user=get_usuario_logado()
        )

    ids = list(map(int, carrinho.keys()))
    placeholders = ",".join(["%s"] * len(ids))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(f"""
        SELECT id, nome, preco_base
        FROM itens_cardapio
        WHERE id IN ({placeholders})
    """, tuple(ids))
    itens_db = {row["id"]: row for row in cur.fetchall()}

    itens = []
    subtotal = 0.0

    for item_id_str, qtd in carrinho.items():
        item_id = int(item_id_str)
        row = itens_db.get(item_id)
        if not row:
            continue

        preco = float(row["preco_base"])
        linha_total = preco * qtd
        subtotal += linha_total

        itens.append({
            "id": item_id,
            "nome": row["nome"],
            "preco": preco,
            "qtd": qtd,
            "linha_total": linha_total
        })

    cur.close()
    db.close()

    return render_template(
        "carrinho.html",
        itens=itens,
        subtotal=subtotal,
        restaurante_id=restaurante_id,
        user=get_usuario_logado()
    )


# =========================
# Checkout (EXIGE CLIENTE LOGADO)
# =========================
@app.get("/checkout")
def checkout():
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]
    carrinho = session.get("carrinho", {})
    restaurante_id = session.get("carrinho_restaurante_id")

    if not carrinho or not restaurante_id:
        return redirect(url_for("home"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT id, rua, numero, bairro, cidade, estado, cep
        FROM enderecos
        WHERE cliente_id=%s
        ORDER BY id DESC
    """, (cliente_id,))
    enderecos = cur.fetchall()

    cur.close()
    db.close()

    return render_template("checkout.html", enderecos=enderecos, user=get_usuario_logado())


@app.post("/checkout")
def finalizar_checkout():
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]
    carrinho = session.get("carrinho", {})
    restaurante_id = session.get("carrinho_restaurante_id")

    if not carrinho or not restaurante_id:
        return redirect(url_for("home"))

    endereco_id = int(request.form["endereco_id"])
    metodo = request.form["metodo"]  # PIX ou CARTAO
    if metodo not in ("PIX", "CARTAO"):
        abort(400)

    taxa_entrega = 7.00  # MVP fixa

    ids = list(map(int, carrinho.keys()))
    placeholders = ",".join(["%s"] * len(ids))

    db = get_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute(f"""
            SELECT id, preco_base
            FROM itens_cardapio
            WHERE id IN ({placeholders})
        """, tuple(ids))
        precos = {row["id"]: float(row["preco_base"]) for row in cur.fetchall()}

        subtotal = 0.0
        for item_id_str, qtd in carrinho.items():
            item_id = int(item_id_str)
            if item_id not in precos:
                raise ValueError("Item inválido no carrinho.")
            subtotal += precos[item_id] * qtd

        total = subtotal + taxa_entrega

        cur.execute("""
            INSERT INTO pedidos (
              cliente_id, restaurante_id, endereco_id,
              status_pedido, taxa_entrega, subtotal, total,
              metodo_pagamento, status_pagamento, valor_pago
            )
            VALUES (%s,%s,%s,'ACEITO',%s,%s,%s,%s,'PAGO',%s)
        """, (cliente_id, restaurante_id, endereco_id, taxa_entrega, subtotal, total, metodo, total))

        pedido_id = cur.lastrowid

        for item_id_str, qtd in carrinho.items():
            item_id = int(item_id_str)
            preco_unit = precos[item_id]
            total_linha = preco_unit * qtd

            cur.execute("""
                INSERT INTO itens_pedido (
                  pedido_id, item_cardapio_id, quantidade,
                  preco_unitario_snapshot, total_linha
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (pedido_id, item_id, qtd, preco_unit, total_linha))

        db.commit()

    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao finalizar pedido: {e}", 400

    cur.close()
    db.close()

    session["carrinho"] = {}
    session["carrinho_restaurante_id"] = None

    return redirect(url_for("ver_pedido", pid=pedido_id))


@app.get("/pedido/<int:pid>")
def ver_pedido(pid):
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT p.*, r.nome AS restaurante_nome
        FROM pedidos p
        JOIN restaurantes r ON r.usuario_id = p.restaurante_id
        WHERE p.id=%s
    """, (pid,))
    pedido = cur.fetchone()
    if not pedido:
        cur.close()
        db.close()
        abort(404)

    cur.execute("""
        SELECT ic.nome, ip.quantidade, ip.total_linha
        FROM itens_pedido ip
        JOIN itens_cardapio ic ON ic.id = ip.item_cardapio_id
        WHERE ip.pedido_id=%s
    """, (pid,))
    itens = cur.fetchall()

    cur.close()
    db.close()

    return render_template("pedido.html", pedido=pedido, itens=itens, user=get_usuario_logado())


# =========================
# Cadastro (CLIENTE ou RESTAURANTE)
# =========================
@app.get("/cadastro")
def cadastro_form():
    return render_template("cadastro.html", user=get_usuario_logado())


@app.post("/cadastro")
def cadastro_salvar():
    email = request.form["email"].strip().lower()
    senha = request.form["senha"]
    tipo = request.form["tipo"]  # CLIENTE ou RESTAURANTE
    nome = request.form["nome"].strip()
    telefone = request.form.get("telefone", "").strip()

    tempo_min = request.form.get("tempo_preparo_min", "").strip()
    tempo_max = request.form.get("tempo_preparo_max", "").strip()

    if tipo not in ("CLIENTE", "RESTAURANTE"):
        abort(400)

    if not email or not senha or not nome:
        return "Erro: email, senha e nome são obrigatórios.", 400

    senha_hash = generate_password_hash(senha)

    db = get_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            INSERT INTO usuarios (email, senha, tipo)
            VALUES (%s, %s, %s)
        """, (email, senha_hash, tipo))
        usuario_id = cur.lastrowid

        if tipo == "CLIENTE":
            cur.execute("""
                INSERT INTO clientes (usuario_id, nome, telefone)
                VALUES (%s, %s, %s)
            """, (usuario_id, nome, telefone if telefone else None))
        else:
            status = "ABERTO"
            tmin = int(tempo_min) if tempo_min else 20
            tmax = int(tempo_max) if tempo_max else 40
            if tmin > tmax:
                return "Erro: tempo mínimo não pode ser maior que o máximo.", 400

            cur.execute("""
                INSERT INTO restaurantes (usuario_id, nome, telefone, status, tempo_preparo_min, tempo_preparo_max)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (usuario_id, nome, telefone if telefone else None, status, tmin, tmax))

        db.commit()

    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao cadastrar: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("login_form"))


# =========================
# Login / Logout
# =========================
@app.get("/login")
def login_form():
    next_url = request.args.get("next", "/")
    return render_template("login.html", next_url=next_url, user=get_usuario_logado())


@app.post("/login")
def login_entrar():
    email = request.form["email"].strip().lower()
    senha = request.form["senha"]
    next_url = request.form.get("next_url", "/")

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT id, email, senha, tipo FROM usuarios WHERE email=%s", (email,))
    u = cur.fetchone()

    cur.close()
    db.close()

    if not u or not check_password_hash(u["senha"], senha):
        return render_template(
            "login.html",
            next_url=next_url,
            erro="Email ou senha inválidos.",
            user=get_usuario_logado()
        )

    session["usuario_id"] = u["id"]
    session["tipo"] = u["tipo"]

    return redirect(next_url)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# =========================
# Endereços do cliente (EXIGE CLIENTE LOGADO)
# =========================
@app.get("/enderecos")
def enderecos_listar():
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT id, rua, numero, bairro, cidade, estado, cep, complemento
        FROM enderecos
        WHERE cliente_id=%s
        ORDER BY id DESC
    """, (cliente_id,))
    enderecos = cur.fetchall()

    cur.close()
    db.close()

    return render_template("enderecos.html", enderecos=enderecos, user=get_usuario_logado())


@app.post("/enderecos")
def enderecos_criar():
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]

    rua = request.form["rua"].strip()
    numero = request.form["numero"].strip()
    bairro = request.form.get("bairro", "").strip()
    cidade = request.form.get("cidade", "").strip()
    estado = request.form.get("estado", "").strip().upper()
    cep = request.form["cep"].strip()
    complemento = request.form.get("complemento", "").strip()

    if not rua or not numero or not cep:
        return "Erro: rua, número e CEP são obrigatórios.", 400

    if estado and len(estado) != 2:
        return "Erro: estado deve ter 2 letras (ex: AM).", 400

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            INSERT INTO enderecos (
              cliente_id, rua, numero, bairro, cidade, estado, cep, complemento
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (cliente_id, rua, numero, bairro or None, cidade or None, estado or None, cep, complemento or None))
        db.commit()
    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao cadastrar endereço: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("enderecos_listar"))


@app.post("/enderecos/<int:eid>/delete")
def enderecos_deletar(eid):
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("DELETE FROM enderecos WHERE id=%s AND cliente_id=%s", (eid, cliente_id))
        db.commit()
    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao deletar endereço: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("enderecos_listar"))

# =========================
# Pedidos do cliente (EXIGE CLIENTE LOGADO)
# =========================
@app.get("/meus-pedidos")
def cliente_pedidos():
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT
          p.id,
          p.realizado_em,
          p.status_pedido,
          p.total,
          p.entregue_em,
          r.nome AS restaurante_nome
        FROM pedidos p
        JOIN restaurantes r ON r.usuario_id = p.restaurante_id
        WHERE p.cliente_id=%s
        ORDER BY p.realizado_em DESC
    """, (cliente_id,))
    pedidos = cur.fetchall()

    cur.close()
    db.close()

    return render_template("meus_pedidos.html", pedidos=pedidos, user=get_usuario_logado())


@app.get("/meus-pedidos/<int:pid>")
def cliente_pedido_detalhe(pid):
    bloqueio = exigir_login("CLIENTE")
    if bloqueio:
        return bloqueio

    cliente_id = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT
          p.*,
          r.nome AS restaurante_nome
        FROM pedidos p
        JOIN restaurantes r ON r.usuario_id = p.restaurante_id
        WHERE p.id=%s AND p.cliente_id=%s
    """, (pid, cliente_id))
    pedido = cur.fetchone()
    if not pedido:
        cur.close()
        db.close()
        abort(404)

    cur.execute("""
        SELECT ic.nome, ip.quantidade, ip.total_linha
        FROM itens_pedido ip
        JOIN itens_cardapio ic ON ic.id = ip.item_cardapio_id
        WHERE ip.pedido_id=%s
    """, (pid,))
    itens = cur.fetchall()

    cur.close()
    db.close()

    return render_template("meu_pedido_detalhe.html", pedido=pedido, itens=itens, user=get_usuario_logado())

# =========================
# Painel do restaurante (home)
# =========================
@app.get("/restaurante")
def restaurante_home():
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT usuario_id, nome, status FROM restaurantes WHERE usuario_id=%s", (rid,))
    rest = cur.fetchone()

    cur.close()
    db.close()

    if not rest:
        return "Restaurante não encontrado para este usuário.", 400

    return render_template("restaurante_home.html", restaurante=rest, user=get_usuario_logado())


# =========================
# Pedidos do restaurante (listar + detalhe + marcar entregue)
# =========================
@app.get("/restaurante/pedidos")
def restaurante_pedidos():
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT p.id, p.realizado_em, p.status_pedido, p.total, c.nome AS cliente_nome
        FROM pedidos p
        JOIN clientes c ON c.usuario_id = p.cliente_id
        WHERE p.restaurante_id=%s
        ORDER BY p.realizado_em DESC
    """, (rid,))
    pedidos = cur.fetchall()

    cur.close()
    db.close()

    return render_template("painel_pedidos.html", pedidos=pedidos, rid=rid, user=get_usuario_logado())


@app.get("/restaurante/pedidos/<int:pid>")
def restaurante_pedido_detalhe(pid):
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT p.id, p.realizado_em, p.status_pedido, p.total, c.nome AS cliente_nome
        FROM pedidos p
        JOIN clientes c ON c.usuario_id = p.cliente_id
        WHERE p.id=%s AND p.restaurante_id=%s
    """, (pid, rid))
    pedido = cur.fetchone()

    if not pedido:
        cur.close()
        db.close()
        abort(404)

    cur.execute("""
        SELECT ic.nome, ip.quantidade, ip.total_linha
        FROM itens_pedido ip
        JOIN itens_cardapio ic ON ic.id = ip.item_cardapio_id
        WHERE ip.pedido_id=%s
    """, (pid,))
    itens = cur.fetchall()

    cur.close()
    db.close()

    return render_template("pedido_detalhe_restaurante.html", pedido=pedido, itens=itens, user=get_usuario_logado())


@app.post("/restaurante/pedidos/<int:pid>/entregar")
def restaurante_marcar_entregue(pid):
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            UPDATE pedidos
            SET status_pedido='ENTREGUE', entregue_em=NOW()
            WHERE id=%s AND restaurante_id=%s
              AND status_pedido <> 'CANCELADO'
        """, (pid, rid))

        if cur.rowcount == 0:
            db.rollback()
            cur.close()
            db.close()
            return "Pedido não encontrado, não pertence a este restaurante ou não pode ser atualizado.", 400

        db.commit()

    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao atualizar pedido: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("restaurante_pedidos"))


# =========================
# Cardápio do restaurante (CRUD) - EXIGE RESTAURANTE LOGADO
# =========================
@app.get("/restaurante/cardapio")
def restaurante_cardapio():
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT id, nome, descricao, preco_base, disponivel
        FROM itens_cardapio
        WHERE restaurante_id=%s
        ORDER BY nome
    """, (rid,))
    itens = cur.fetchall()

    cur.close()
    db.close()

    return render_template("restaurante_cardapio.html", itens=itens, user=get_usuario_logado())


@app.get("/restaurante/cardapio/novo")
def restaurante_cardapio_novo_form():
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    return render_template("restaurante_cardapio_form.html", item=None, acao="novo", user=get_usuario_logado())


@app.post("/restaurante/cardapio/novo")
def restaurante_cardapio_criar():
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    nome = request.form["nome"].strip()
    descricao = request.form.get("descricao", "").strip()
    preco = request.form["preco_base"].strip()
    disponivel = 1 if request.form.get("disponivel") == "on" else 0

    if not nome:
        return "Erro: nome é obrigatório.", 400

    try:
        preco_val = float(preco)
        if preco_val <= 0:
            return "Erro: preço deve ser maior que zero.", 400
    except:
        return "Erro: preço inválido.", 400

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            INSERT INTO itens_cardapio (restaurante_id, nome, descricao, preco_base, disponivel)
            VALUES (%s,%s,%s,%s,%s)
        """, (rid, nome, descricao or None, preco_val, disponivel))
        db.commit()
    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao criar item: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("restaurante_cardapio"))


@app.get("/restaurante/cardapio/<int:item_id>/editar")
def restaurante_cardapio_editar_form(item_id):
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT id, nome, descricao, preco_base, disponivel
        FROM itens_cardapio
        WHERE id=%s AND restaurante_id=%s
    """, (item_id, rid))
    item = cur.fetchone()

    cur.close()
    db.close()

    if not item:
        abort(404)

    return render_template("restaurante_cardapio_form.html", item=item, acao="editar", user=get_usuario_logado())


@app.post("/restaurante/cardapio/<int:item_id>/editar")
def restaurante_cardapio_atualizar(item_id):
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    nome = request.form["nome"].strip()
    descricao = request.form.get("descricao", "").strip()
    preco = request.form["preco_base"].strip()
    disponivel = 1 if request.form.get("disponivel") == "on" else 0

    if not nome:
        return "Erro: nome é obrigatório.", 400

    try:
        preco_val = float(preco)
        if preco_val <= 0:
            return "Erro: preço deve ser maior que zero.", 400
    except:
        return "Erro: preço inválido.", 400

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            UPDATE itens_cardapio
            SET nome=%s, descricao=%s, preco_base=%s, disponivel=%s
            WHERE id=%s AND restaurante_id=%s
        """, (nome, descricao or None, preco_val, disponivel, item_id, rid))

        if cur.rowcount == 0:
            db.rollback()
            cur.close()
            db.close()
            abort(404)

        db.commit()
    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao atualizar item: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("restaurante_cardapio"))


@app.post("/restaurante/cardapio/<int:item_id>/delete")
def restaurante_cardapio_desativar(item_id):
    """
    Em vez de DELETE (que pode quebrar por FK em itens_pedido),
    desativamos: disponivel=0.
    """
    bloqueio = exigir_login("RESTAURANTE")
    if bloqueio:
        return bloqueio

    rid = session["usuario_id"]

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            UPDATE itens_cardapio
            SET disponivel=0
            WHERE id=%s AND restaurante_id=%s
        """, (item_id, rid))

        if cur.rowcount == 0:
            db.rollback()
            cur.close()
            db.close()
            abort(404)

        db.commit()

    except Exception as e:
        db.rollback()
        cur.close()
        db.close()
        return f"Erro ao desativar item: {e}", 400

    cur.close()
    db.close()

    return redirect(url_for("restaurante_cardapio"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)