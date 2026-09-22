// Permite configurar a URL da API no HTML quando o sistema for publicado.
const API = window.SCRIM_API_URL || "http://127.0.0.1:8000";
let token = localStorage.getItem("scrim_token"),
  user = safeJson(localStorage.getItem("scrim_user")),
  materials = [],
  categories = [];

function safeJson(value) {
  try {
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

// Evita que dados cadastrados sejam interpretados como HTML na tela.
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>\"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  })[char]);
}
async function api(path, opt = {}) {
  let h = { "Content-Type": "application/json", ...(opt.headers || {}) };
  if (token) h.Authorization = "Bearer " + token;
  let r = await fetch(API + path, { ...opt, headers: h }),
    d = await r.json().catch(() => null);
  if (!r.ok) {
    // Token expirado ou invalido: volta ao login em vez de mostrar dados zerados.
    if (r.status === 401 && token) logout();
    const detalhe = Array.isArray(d?.detail)
      ? d.detail.map((item) => item.msg || "Dados inválidos").join(". ")
      : d?.detail;
    throw Error(detalhe || `Erro no servidor (HTTP ${r.status}). Verifique o terminal da API.`);
  }
  return d;
}

function showPageError(message) {
  document.getElementById("content").innerHTML =
    `<div class="page"><p class="error-message">${escapeHtml(message)}</p></div>`;
}
function openSignup() {
  showModal('<div class="modal-box signup-box"><button class="x" type="button" onclick="closeModal()">×</button><div class="auth-brand compact"><div class="brand-mark"><i>★</i></div><b>SCRIM</b><small>SISTEMA DE CONTROLE DE MATERIAIS</small></div><h2>Criar conta</h2><p class="muted">Preencha os dados para solicitar seu acesso.</p><form id="signupForm"><label>TIPO DE CONTA<select id="signupType" required onchange="toggleMilitaryId()"><option value="cliente">Usuário comum</option><option value="admin">Administrador</option></select></label><label>NOME<input id="signupName" required minlength="2" autocomplete="name" placeholder="Seu nome completo"></label><label>E-MAIL<input id="signupEmail" type="email" required autocomplete="email" placeholder="seu@email.com"></label><label id="signupMilitaryIdField" hidden>ID MILITAR<input id="signupMilitaryId" autocomplete="off" placeholder="Informe seu ID militar"></label><label>TELEFONE <span class="optional">(opcional)</span><input id="signupPhone" type="tel" autocomplete="tel" placeholder="+5511999999999"></label><label>SENHA<input id="signupPassword" type="password" required minlength="6" autocomplete="new-password" placeholder="Mínimo de 6 caracteres"></label><small id="signupError"></small><button class="btn green" type="submit">CRIAR CONTA</button></form></div>');
  document.getElementById("signupForm").onsubmit = signup;
}
function toggleMilitaryId() {
  const isAdmin = document.getElementById("signupType").value === "admin";
  const field = document.getElementById("signupMilitaryIdField");
  const input = document.getElementById("signupMilitaryId");
  field.hidden = !isAdmin;
  input.required = isAdmin;
  if (!isAdmin) input.value = "";
}
async function signup(e) {
  e.preventDefault();
  let error = document.getElementById("signupError");
  error.textContent = "";
  try {
    const cadastro = {
      nome: document.getElementById("signupName").value,
      email: document.getElementById("signupEmail").value,
      telefone: document.getElementById("signupPhone").value || null,
      senha: document.getElementById("signupPassword").value,
      tipo: document.getElementById("signupType").value,
      id_militar: document.getElementById("signupMilitaryId").value || null,
    };
    await api("/auth/registrar", {
      method: "POST",
      body: JSON.stringify(cadastro),
    });
    const dadosLogin = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: cadastro.email, senha: cadastro.senha }),
    });
    closeModal();
    autenticar(dadosLogin);
  } catch (e) {
    error.textContent = e.message;
  }
}
function autenticar(dados) {
  token = dados.access_token;
  user = dados.usuario;
  localStorage.setItem("scrim_token", token);
  localStorage.setItem("scrim_user", JSON.stringify(user));
  start();
}
document.getElementById("loginForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    let d = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("email").value,
        senha: document.getElementById("senha").value,
      }),
    });
    autenticar(d);
  } catch (e) {
    document.getElementById("error").textContent = e.message;
  }
};
function start() {
  if (!user?.nome || !token) return logout();
  document.getElementById("login").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  document.getElementById("initial").textContent = user.nome[0].toUpperCase();
  document.getElementById("userName").textContent = user.nome;
  document.getElementById("topName").textContent = user.nome.split(" ")[0];
  document.getElementById("userType").textContent = user.tipo === "admin" ? "Administrador" : "Cliente";
  document
    .querySelectorAll(".admin")
    .forEach(
      (x) => (x.style.display = user.tipo === "admin" ? "block" : "none"),
    );
  page("home");
}
function logout() {
  localStorage.removeItem("scrim_token");
  localStorage.removeItem("scrim_user");
  location.reload();
}
document
  .querySelectorAll("nav button")
  .forEach((b) => (b.onclick = () => page(b.dataset.page)));
async function page(p) {
  if (["estoque", "categorias", "usuarios"].includes(p) && user.tipo !== "admin") {
    return showPageError("Acesso restrito a administradores.");
  }
  document.getElementById("title").textContent = {
    home: "DASHBOARD",
    materiais: "MATERIAIS",
    emprestimos: "EMPRÉSTIMOS",
    estoque: "ESTOQUE",
    categorias: "CATEGORIAS",
    usuarios: "USUÁRIOS",
    perfil: "MEU PERFIL",
  }[p] || "SCRIM";
  document.querySelectorAll("nav button").forEach((button) =>
    button.classList.toggle("active", button.dataset.page === p),
  );
  if (p === "home") home();
  if (p === "materiais") materiaisPage();
  if (p === "emprestimos") emprestimos();
  if (p === "estoque") estoque();
  if (p === "categorias") cats();
  if (p === "usuarios") usuarios();
  if (p === "perfil") perfil();
}
async function home() {
  let ms = [],
    ls = [];
  try {
    ms = await api("/materiais?somente_ativos=true&limit=500");
  } catch (e) {
    showPageError(e.message);
    return;
  }
  try {
    ls = await api("/emprestimos?limit=500");
  } catch (e) {
    showPageError(e.message);
    return;
  }
  content.innerHTML = `<div class="page"><div class="head"><div><span class="eyebrow2">CENTRO DE CONTROLE</span><h1>Olá, ${user.nome.split(" ")[0]}.</h1><p>Controle de materiais e empréstimos.</p></div></div><div class="stats"><div class="stat"><small>MATERIAIS</small><b>${ms.length}</b></div><div class="stat"><small>DISPONÍVEIS</small><b>${ms.filter((m) => m.quantidade_disponivel > 0).length}</b></div><div class="stat"><small>EM USO</small><b>${ls.filter((l) => l.status === "ativo" || l.status === "atrasado").length}</b></div><div class="stat"><small>ATRASADOS</small><b>${ls.filter((l) => l.status === "atrasado").length}</b></div></div><div class="grid"><section class="panel"><h3>Empréstimos recentes</h3>${
    ls
      .slice(0, 6)
      .map(
        (l) =>
          `<div class="activity"><span>↕ Empréstimo #${l.id} — Material #${l.material_id}</span><b>${l.status}</b></div>`,
      )
      .join("") || "<p class=muted>Nenhum empréstimo.</p>"
  }</section><section class="panel"><h3>Acesso rápido</h3><div class="quick"><button onclick="page('materiais')">▣ Consultar materiais</button><button onclick="page('emprestimos')">↕ Meus empréstimos</button>${user.tipo === "admin" ? "<button onclick=\"page('estoque')\">▤ Controle de estoque</button><button onclick=\"page('usuarios')\">♙ Usuários</button>" : ""}</div></section></div></div>`;
}
async function materiaisPage() {
  try {
    categories = await api("/categorias");
    materials = await api("/materiais?somente_ativos=true&limit=500");
  } catch (e) {
    showPageError(e.message);
    return;
  }
  content.innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>INVENTÁRIO</span><h1>Materiais</h1><p>Escolha um material disponível para realizar um empréstimo.</p></div>${user.tipo === "admin" ? '<button class="btn green" onclick="newMaterial()">+ Novo material</button>' : ""}</div><div class=filters><input id=search placeholder="🔎 Pesquisar material ou código" oninput=filterMat()><select id=catFilter onchange=filterMat()><option value="">Todas as categorias</option>${categories.map((c) => `<option value="${c.id}">${c.nome}</option>`).join("")}</select></div><div id=matCards class=cards></div></div>`;
  filterMat();
}

// Cadastro administrativo de materiais: a quantidade inicial gera uma movimentação
// de entrada automaticamente no backend, mantendo o histórico de estoque íntegro.
function newMaterial() {
  if (!categories.length) return alert("Cadastre uma categoria antes de criar um material.");
  showModal(`<div class=modal-box><button class=x type=button onclick=closeModal()>×</button><h2>Novo material</h2><form id=materialForm><label>NOME<input id=mn required minlength=2></label><label>CÓDIGO<input id=mc required></label><label>CATEGORIA<select id=mcat required>${categories.map((c) => `<option value="${c.id}">${escapeHtml(c.nome)}</option>`).join("")}</select></label><label>QUANTIDADE INICIAL<input id=mqt type=number min=0 value=0 required></label><label>PRAZO MÁXIMO (DIAS)<input id=mp type=number min=1 value=7 required></label><label>DESCRIÇÃO<textarea id=md></textarea></label><small id=materialError></small><button class="btn green" type=submit>CADASTRAR</button></form></div>`);
  const form = document.getElementById("materialForm");
  const imageField = document.createElement("label");
  imageField.className = "image-upload";
  imageField.innerHTML = 'IMAGEM DO MATERIAL <span>📷 Selecionar PNG</span><input id="mi" type="file" accept="image/png">';
  form.querySelector("#materialError").before(imageField);
  form.onsubmit = createMaterial;
}

async function createMaterial(event) {
  event.preventDefault();
  const error = document.getElementById("materialError");
  try {
    const material = await api("/materiais", {
      method: "POST",
      body: JSON.stringify({
        nome: document.getElementById("mn").value,
        codigo: document.getElementById("mc").value,
        categoria_id: Number(document.getElementById("mcat").value),
        quantidade_total: Number(document.getElementById("mqt").value),
        tempo_maximo_dias: Number(document.getElementById("mp").value),
        descricao: document.getElementById("md").value || null,
      }),
    });
    const imagem = document.getElementById("mi").files[0];
    if (imagem) {
      try {
        await uploadMaterialImage(material.id, imagem);
      } catch (uploadError) {
        // O material já foi criado; informa a falha sem induzir novo cadastro duplicado.
        closeModal();
        materiaisPage();
        alert(`Material criado, mas a imagem não foi enviada: ${uploadError.message}`);
        return;
      }
    }
    closeModal();
    materiaisPage();
  } catch (e) {
    error.textContent = e.message;
  }
}

// Upload usa FormData; por isso o Content-Type é definido automaticamente pelo navegador.
async function uploadMaterialImage(materialId, image) {
  if (image.type !== "image/png") throw Error("Selecione uma imagem no formato PNG.");
  if (image.size > 5 * 1024 * 1024) throw Error("A imagem deve ter no máximo 5 MB.");
  const formData = new FormData();
  formData.append("imagem", image);
  const response = await fetch(`${API}/materiais/${materialId}/imagem`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw Error(data?.detail || "Não foi possível enviar a imagem.");
  return data;
}

function filterMatAntigo() {
  let q = (document.getElementById("search")?.value || "").toLowerCase(),
    c = document.getElementById("catFilter")?.value || "";
  let a = materials.filter(
    (m) =>
      (!q ||
        m.nome.toLowerCase().includes(q) ||
        m.codigo.toLowerCase().includes(q)) &&
      (!c || String(m.categoria_id) === c),
  );
  matCards.innerHTML =
    a
      .map(
        (m) =>
          `<article class=card><span class="badge ${m.quantidade_disponivel ? "" : "red"}">${m.quantidade_disponivel ? "DISPONÍVEL" : "INDISPONÍVEL"}</span><h3>▣ ${m.nome}</h3><span class=muted>Código: ${m.codigo}</span><div class=material-info><div>DISPONÍVEL<b>${m.quantidade_disponivel}/${m.quantidade_total}</b></div><div>PRAZO<b>${m.tempo_maximo_dias} dias</b></div></div><button class="btn" onclick="details(${m.id})">Detalhes</button>${m.quantidade_disponivel ? ` <button class="btn green" onclick="borrow(${m.id})">PEGAR</button>` : ""}</article>`,
      )
      .join("") || "<p class=muted>Nenhum material encontrado.</p>";
}
// Renderizacao segura dos cards de materiais (nomes e codigos podem vir do banco).
function filterMat() {
  const search = (document.getElementById("search")?.value || "").toLowerCase();
  const categoryId = document.getElementById("catFilter")?.value || "";
  const visible = materials.filter((item) =>
    (!search || item.nome.toLowerCase().includes(search) || item.codigo.toLowerCase().includes(search)) &&
    (!categoryId || String(item.categoria_id) === categoryId),
  );
  document.getElementById("matCards").innerHTML = visible.map((item) =>
    `<article class=card><span class="badge ${item.quantidade_disponivel ? "" : "red"}">${item.quantidade_disponivel ? "DISPONIVEL" : "INDISPONIVEL"}</span>${item.imagem_url ? `<img class="material-image" src="${API}${encodeURI(item.imagem_url)}" alt="Imagem de ${escapeHtml(item.nome)}">` : '<div class="material-image material-image-empty">Sem imagem</div>'}<h3>${escapeHtml(item.nome)}</h3><span class=muted>Codigo: ${escapeHtml(item.codigo)}</span><div class=material-info><div>DISPONIVEL<b>${item.quantidade_disponivel}/${item.quantidade_total}</b></div><div>PRAZO<b>${item.tempo_maximo_dias} dias</b></div></div><button class=btn onclick="details(${item.id})">Detalhes</button>${item.quantidade_disponivel ? ` <button class="btn green" onclick="borrow(${item.id})">PEGAR</button>` : ""}</article>`,
  ).join("") || "<p class=muted>Nenhum material encontrado.</p>";
}

async function details(id) {
  let m = await api("/materiais/" + id);
  modal(
    `<div class=modal-box><button class=x onclick=closeModal()>×</button><h2>${m.nome}</h2><p>${m.descricao || "Sem descrição."}</p><p><b>Categoria:</b> ${m.categoria?.nome || "—"}<br><b>Disponível:</b> ${m.quantidade_disponivel}<br><b>Prazo:</b> ${m.tempo_maximo_dias} dias</p>${m.quantidade_disponivel ? `<button class="btn green" onclick="closeModal();borrow(${m.id})">PEGAR MATERIAL</button>` : ""}</div>`,
  );
}
function borrow(id) {
  let m = materials.find((x) => x.id === id);
  modal(
    `<div class=modal-box><button class=x onclick=closeModal()>×</button><h2>Pegar ${m.nome}</h2><p class=muted>Disponível: ${m.quantidade_disponivel}</p><label>QUANTIDADE<input id=bq type=number min=1 max=${m.quantidade_disponivel} value=1></label><button class="btn green" onclick=sendBorrow(${id})>CONFIRMAR EMPRÉSTIMO</button></div>`,
  );
}
async function sendBorrow(id) {
  try {
    await api("/emprestimos", {
      method: "POST",
      body: JSON.stringify({ material_id: id, quantidade: Number(bq.value) }),
    });
    closeModal();
    alert("Empréstimo registrado.");
    materiaisPage();
  } catch (e) {
    alert(e.message);
  }
}
async function emprestimosAntigo() {
  try {
    let ls = await api("/emprestimos");
    content.innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>${user.tipo === "admin" ? "CONTROLE ADMINISTRATIVO" : "ACOMPANHAMENTO"}</span><h1>${user.tipo === "admin" ? "Empréstimos" : "Meus empréstimos"}</h1><p>${user.tipo === "admin" ? "Veja quem pegou cada material." : "Veja os materiais que você pegou."}</p></div></div><div class=table><table><thead><tr><th>ID</th><th>MATERIAL</th>${user.tipo === "admin" ? "<th>USUÁRIO</th>" : ""}<th>QTD</th><th>RETIRADA</th><th>DEVOLUÇÃO</th><th>STATUS</th></tr></thead><tbody>${ls.map((l) => `<tr><td>#${l.id}</td><td>Material #${l.material_id}</td>${user.tipo === "admin" ? `<td>Usuário #${l.usuario_id}</td>` : ""}<td>${l.quantidade}</td><td>${date(l.data_emprestimo)}</td><td>${date(l.data_devolucao_prevista)}</td><td>${l.status.toUpperCase()}</td></tr>`).join("")}</tbody></table></div></div>`;
  } catch (e) {
    content.innerHTML = `<div class=page><p>${e.message}</p></div>`;
  }
}
// A lista usa nomes, e não apenas IDs, e expõe as ações administrativas que a API já oferece.
async function emprestimos() {
  try {
    const requisicoes = [
      api("/emprestimos?limit=500"),
      api("/materiais?somente_ativos=false&limit=500"),
    ];
    if (user.tipo === "admin") requisicoes.push(api("/usuarios?limit=500"));
    const [loans, allMaterials, users = []] = await Promise.all(requisicoes);
    const materialNames = new Map(allMaterials.map((item) => [item.id, item.nome]));
    const userNames = new Map(users.map((item) => [item.id, item.nome]));
    const rows = loans.map((loan) => {
      const actions = user.tipo === "admin" && ["ativo", "atrasado"].includes(loan.status)
        ? `<button class="btn" onclick="returnLoan(${loan.id})">Devolver</button> <button class="btn" onclick="notifyLoan(${loan.id}, '${loan.status}')">WhatsApp</button>`
        : "-";
      return `<tr><td>#${loan.id}</td><td>${escapeHtml(materialNames.get(loan.material_id) || `Material #${loan.material_id}`)}</td>${user.tipo === "admin" ? `<td>${escapeHtml(userNames.get(loan.usuario_id) || `Usuario #${loan.usuario_id}`)}</td>` : ""}<td>${loan.quantidade}</td><td>${date(loan.data_emprestimo)}</td><td>${date(loan.data_devolucao_prevista)}</td><td>${escapeHtml(loan.status.toUpperCase())}</td>${user.tipo === "admin" ? `<td>${actions}</td>` : ""}</tr>`;
    }).join("") || `<tr><td colspan="${user.tipo === "admin" ? 8 : 6}" class="muted">Nenhum emprestimo encontrado.</td></tr>`;
    document.getElementById("content").innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>ACOMPANHAMENTO</span><h1>${user.tipo === "admin" ? "Emprestimos" : "Meus emprestimos"}</h1><p>Historico e situacao das retiradas.</p></div></div><div class=table><table><thead><tr><th>ID</th><th>MATERIAL</th>${user.tipo === "admin" ? "<th>USUARIO</th>" : ""}<th>QTD</th><th>RETIRADA</th><th>PREVISTA</th><th>STATUS</th>${user.tipo === "admin" ? "<th>ACOES</th>" : ""}</tr></thead><tbody>${rows}</tbody></table></div></div>`;
  } catch (e) {
    showPageError(e.message);
  }
}

async function returnLoan(id) {
  if (!confirm("Confirmar a devolucao fisica deste material?")) return;
  try {
    await api(`/emprestimos/${id}/devolver`, { method: "PATCH" });
    emprestimos();
  } catch (e) {
    alert(e.message);
  }
}

async function notifyLoan(id, status) {
  const tipo = status === "atrasado" ? "atraso" : "lembrete_devolucao";
  try {
    await api(`/emprestimos/${id}/whatsapp`, {
      method: "POST",
      body: JSON.stringify({ tipo }),
    });
    alert("Mensagem enviada.");
  } catch (e) {
    alert(e.message);
  }
}

async function estoque() {
  let ms = await api("/materiais?somente_ativos=true");
  content.innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>ADMINISTRAÇÃO</span><h1>Controle de estoque</h1><p>Entradas, perdas, danos e ajustes.</p></div></div><div class=table><table><thead><tr><th>MATERIAL</th><th>TOTAL</th><th>EMPRESTADO</th><th>DISPONÍVEL</th><th></th></tr></thead><tbody>${ms.map((m) => `<tr><td>${m.nome}</td><td>${m.quantidade_total}</td><td>${m.quantidade_emprestada}</td><td>${m.quantidade_disponivel}</td><td><button class=btn onclick="movement(${m.id})">Movimentar</button></td></tr>`).join("")}</tbody></table></div></div>`;
}
function movement(id) {
  modal(
    `<div class=modal-box><button class=x onclick=closeModal()>×</button><h2>Movimentar estoque</h2><label>TIPO<select id=mt><option>entrada</option><option>perda</option><option>danificado</option><option>ajuste</option></select></label><label>QUANTIDADE<input id=mq type=number min=1 required></label><label>MOTIVO<textarea id=mm></textarea></label><button class="btn green" onclick=sendMovement(${id})>REGISTRAR</button></div>`,
  );
}
async function sendMovement(id) {
  try {
    await api("/materiais/" + id + "/movimentacoes", {
      method: "POST",
      body: JSON.stringify({
        tipo: mt.value,
        quantidade: Number(mq.value),
        motivo: mm.value,
      }),
    });
    closeModal();
    estoque();
  } catch (e) {
    alert(e.message);
  }
}
async function cats() {
  categories = await api("/categorias");
  content.innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>FILTROS</span><h1>Categorias</h1><p>Usadas para organizar e filtrar os materiais.</p></div><button class="btn green" onclick=newCat()>+ Nova categoria</button></div><div class=cards>${categories.map((c) => `<article class=card><h3>⌗ ${c.nome}</h3><p class=muted>${c.descricao || "Sem descrição."}</p><button class=btn onclick=editCat(${c.id})>Editar</button> <button class=btn onclick=delCat(${c.id})>Excluir</button></article>`).join("")}</div></div>`;
}
function newCat() {
  modal(
    `<div class=modal-box><button class=x onclick=closeModal()>×</button><h2>Nova categoria</h2><label>NOME<input id=cn></label><label>DESCRIÇÃO<textarea id=cd></textarea></label><button class="btn green" onclick=createCat()>CRIAR</button></div>`,
  );
}
async function createCat() {
  try {
    await api("/categorias", {
      method: "POST",
      body: JSON.stringify({ nome: cn.value, descricao: cd.value }),
    });
    closeModal();
    cats();
  } catch (e) {
    alert(e.message);
  }
}
async function editCat(id) {
  let c = categories.find((x) => x.id === id);
  modal(
    `<div class=modal-box><button class=x onclick=closeModal()>×</button><h2>Editar categoria</h2><label>NOME<input id=cn value="${c.nome}"></label><label>DESCRIÇÃO<textarea id=cd>${c.descricao || ""}</textarea></label><button class="btn green" onclick="updateCat(${id})">SALVAR</button></div>`,
  );
}
async function updateCat(id) {
  try {
    await api("/categorias/" + id, {
      method: "PUT",
      body: JSON.stringify({ nome: cn.value, descricao: cd.value }),
    });
    closeModal();
    cats();
  } catch (e) {
    alert(e.message);
  }
}
async function delCat(id) {
  if (confirm("Excluir categoria?"))
    try {
      await api("/categorias/" + id, { method: "DELETE" });
      cats();
    } catch (e) {
      alert(e.message);
    }
}
async function usuarios() {
  let us = await api("/usuarios");
  content.innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>ADMINISTRAÇÃO</span><h1>Usuários</h1><p>Clientes e administradores.</p></div></div><div class=table><table><thead><tr><th>NOME</th><th>E-MAIL</th><th>TELEFONE</th><th>TIPO</th><th>STATUS</th></tr></thead><tbody>${us.map((u) => `<tr><td>${u.nome}</td><td>${u.email}</td><td>${u.telefone || "—"}</td><td>${u.tipo}</td><td>${u.ativo ? "ATIVO" : "INATIVO"}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function perfilAntigo() {
  content.innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>CONTA</span><h1>Meu perfil</h1></div></div><div class=profile><section class=profile-card><div class=avatar>${user.nome[0]}</div><h2>${user.nome}</h2><p>${user.tipo.toUpperCase()}</p></section><section class=panel><h3>Dados pessoais</h3><label>NOME<input disabled value="${user.nome}"></label><label>E-MAIL<input disabled value="${user.email}"></label><label>TELEFONE<input disabled value="${user.telefone || "Não informado"}"></label></section></div></div>`;
}
function perfil() {
  document.getElementById("content").innerHTML = `<div class=page><div class=head><div><span class=eyebrow2>CONTA</span><h1>Meu perfil</h1><p>Informacoes da sua conta.</p></div></div><div class=profile><section class=profile-card><div class=avatar>${escapeHtml(user.nome[0])}</div><h2>${escapeHtml(user.nome)}</h2><p>${escapeHtml(user.tipo.toUpperCase())}</p></section><section class=panel><h3>Dados pessoais</h3><label>NOME<input disabled value="${escapeHtml(user.nome)}"></label><label>E-MAIL<input disabled value="${escapeHtml(user.email)}"></label><label>TELEFONE<input disabled value="${escapeHtml(user.telefone || "Nao informado")}"></label><button class="btn danger" type=button onclick="openDeleteProfile()">Excluir meu perfil</button></section></div></div>`;
}

function openDeleteProfile() {
  showModal('<div class="modal-box delete-profile"><button class="x" type="button" onclick="closeModal()">×</button><h2>Excluir perfil</h2><p>Esta acao desativa sua conta e encerra seu acesso. Seu historico permanece preservado.</p><form id="deleteProfileForm"><label>DIGITE EXCLUIR PARA CONFIRMAR<input id="deleteConfirmation" required></label><label>SUA SENHA<input id="deletePassword" type="password" required autocomplete="current-password"></label><small id="deleteProfileError"></small><button class="btn danger" type="submit">EXCLUIR PERFIL</button></form></div>');
  document.getElementById("deleteProfileForm").onsubmit = deleteProfile;
}

async function deleteProfile(event) {
  event.preventDefault();
  const error = document.getElementById("deleteProfileError");
  if (document.getElementById("deleteConfirmation").value.trim().toUpperCase() !== "EXCLUIR") {
    error.textContent = 'Digite exatamente "EXCLUIR" para confirmar.';
    return;
  }
  try {
    await api("/auth/me", {
      method: "DELETE",
      body: JSON.stringify({ senha: document.getElementById("deletePassword").value }),
    });
    localStorage.removeItem("scrim_token");
    localStorage.removeItem("scrim_user");
    location.reload();
  } catch (e) {
    error.textContent = e.message;
  }
}

function modal(x) {
  document.getElementById("modal").innerHTML =
    "<div class=modal-bg>" + x + "</div>";
  document.getElementById("modal").classList.remove("hidden");
}

// Mantém as chamadas antigas e evita conflito entre a função e o elemento #modal.
function showModal(x) {
  modal(x);
}

function closeModal() {
  document.getElementById("modal").classList.add("hidden");
  document.getElementById("modal").innerHTML = "";
}
function date(x) {
  return x ? new Date(x).toLocaleDateString("pt-BR") : "—";
}
if (token && user) start();
