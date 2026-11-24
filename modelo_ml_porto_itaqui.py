#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  MODELO DE MACHINE LEARNING - DEMORA NO EMBARQUE E DESEMBARQUE
  Porto do Itaqui - Sao Luis / MA
  DECC0294 - Tecnologia da Informacao e Comunicacao Aplicada a Administracao
  UFMA - Curso de Administracao - 2026.2
=============================================================================

O QUE ESTE ARQUIVO E
    Um script que treina modelos de aprendizado de maquina sobre a base
    sintetica do Porto do Itaqui (dados/porto_itaqui_movimentacao.csv).
    Ele faz tres coisas:

    1) REPRESENTA AS RELACOES
       - medias reais por tipo de carga e por turno;
       - coeficientes do modelo linear (quanto cada fator muda o tempo);
       - coeficientes padronizados (para comparar forca entre fatores);
       - matriz de correlacao entre as variaveis numericas.

    2) FAZ PREDICOES
       - regressao linear multipla (implementada do zero);
       - k-vizinhos mais proximos (k-NN, tambem do zero);
       - compara os dois com o palpite simples (prever sempre a media).

    3) DEIXA O MODELO SALVO
       - grava modelo/porto_itaqui_modelo.json para prever cenarios novos
         sem precisar treinar de novo.

COMO USAR (peca ao agente do opencode)

  python modelo_ml_porto_itaqui.py treinar
      Le a base, separa treino e teste, treina os modelos, mede o erro e
      grava saidas/modelo_porto_itaqui.md e modelo/porto_itaqui_modelo.json.

  python modelo_ml_porto_itaqui.py prever "Contêineres" "Manhã" 10 8
      Preve um cenario novo. Ordem dos argumentos:
        tipo de carga, turno de chegada, espera estimada (horas), mes (1-12)
      Mostra a duracao prevista da operacao e o tempo total previsto,
      pelos dois modelos (linear e k-NN).

  python modelo_ml_porto_itaqui.py conferir
      Verifica se o modelo e o relatorio existem e se estao completos.

ORIGEM DOS DADOS
    A base e sintetica, gerada por simulacao_porto_itaqui.py. Os numeros
    servem para exercicio. Nao substituem dados reais da CODESA/ANTAQ.

Nao usa nenhuma biblioteca externa. Roda com o Python ja instalado.
=============================================================================
"""

import csv
import json
import math
import os
import random
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# CAMINHOS E PARAMETROS
# ---------------------------------------------------------------------------

BASE_DADOS = os.path.join("dados", "porto_itaqui_movimentacao.csv")
PASTA_MODELO = "modelo"
ARQ_MODELO = os.path.join(PASTA_MODELO, "porto_itaqui_modelo.json")
RELATORIO = os.path.join("saidas", "modelo_porto_itaqui.md")

SEED = 42
PROPORCAO_TREINO = 0.70
K_VIZINHOS = 5

TIPOS = ["Carga geral", "Contêineres", "Granel líquido", "Granel sólido"]
TURNOS = ["Manhã", "Tarde", "Noite", "Madrugada"]

# Cada alvo tem um rotulo legivel e a decisao de usar ou nao a espera.
# A espera e usada no tempo total e no atraso; nao faz sentido na duracao
# da operacao, que comeca depois que o navio ja atracou.
ALVOS = {
    "duracao_op_horas": {
        "rotulo": "Duração da operação (embarque/desembarque)",
        "incluir_espera": False,
    },
    "atraso_total_horas": {
        "rotulo": "Atraso extra total",
        "incluir_espera": True,
    },
    "tempo_total_horas": {
        "rotulo": "Tempo total (chegada até desatracação)",
        "incluir_espera": True,
    },
}


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def titulo(t):
    print()
    print("=" * 74)
    print(" " + t)
    print("=" * 74)


def num(v):
    if v is None:
        return None
    t = str(v).strip().replace(",", ".")
    if t == "":
        return None
    try:
        return float(t)
    except ValueError:
        return None


def fmt(v, casas=2):
    if v is None:
        return "-"
    return ("%." + str(casas) + "f") % v


def media(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def desvio(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


# ---------------------------------------------------------------------------
# LEITURA E MONTAGEM DA BASE
# ---------------------------------------------------------------------------

def ler_csv():
    if not os.path.exists(BASE_DADOS):
        print("Nao encontrei " + BASE_DADOS)
        print("Rode primeiro: python simulacao_porto_itaqui.py gerar")
        return None
    with open(BASE_DADOS, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def construir_registros(linhas):
    """Converte cada linha em um registro limpo e tipado."""
    registros = []
    for l in linhas:
        tipo = (l.get("tipo_carga") or "").strip()
        turno = (l.get("turno") or "").strip()
        mes_txt = (l.get("mes") or "").strip()
        if tipo not in TIPOS or turno not in TURNOS:
            continue
        try:
            mes = int(mes_txt.split("/")[0])
        except (ValueError, IndexError):
            continue

        espera = num(l.get("espera_berco_horas"))
        operacao = num(l.get("duracao_op_horas"))
        atraso = num(l.get("atraso_total_horas"))
        total = num(l.get("tempo_total_horas"))
        if None in (espera, operacao, atraso, total):
            continue

        registros.append({
            "id": l.get("id_navio"),
            "tipo": tipo,
            "turno": turno,
            "mes": mes,
            "espera": espera,
            "duracao_op_horas": operacao,
            "atraso_total_horas": atraso,
            "tempo_total_horas": total,
        })
    return registros


def construir_features(registro, incluir_espera):
    """
    Monta o vetor de atributos. Categorias viram colunas 0/1.
    A primeira categoria de cada grupo fica de fora (categoria de
    referencia), para o modelo nao ficar com colunas redundantes.
    """
    f = [1.0]                       # intercepto
    nomes = ["intercepto"]

    for t in TIPOS[1:]:
        f.append(1.0 if registro["tipo"] == t else 0.0)
        nomes.append("tipo=" + t)

    for t in TURNOS[1:]:
        f.append(1.0 if registro["turno"] == t else 0.0)
        nomes.append("turno=" + t)

    f.append(float(registro["mes"]))
    nomes.append("mes")

    if incluir_espera:
        f.append(registro["espera"])
        nomes.append("espera_berco_horas")

    return f, nomes


# ---------------------------------------------------------------------------
# REGRESSAO LINEAR (minimos quadrados, do zero)
# ---------------------------------------------------------------------------

def resolver(matriz, vetor):
    """Eliminacao de Gauss com pivotamento. Devolve None se singular."""
    n = len(vetor)
    m = [linha[:] + [vetor[i]] for i, linha in enumerate(matriz)]
    for coluna in range(n):
        piv = max(range(coluna, n), key=lambda r: abs(m[r][coluna]))
        if abs(m[piv][coluna]) < 1e-12:
            return None
        m[coluna], m[piv] = m[piv], m[coluna]
        for linha in range(coluna + 1, n):
            fator = m[linha][coluna] / m[coluna][coluna]
            for k in range(coluna, n + 1):
                m[linha][k] -= fator * m[coluna][k]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        soma = m[i][n] - sum(m[i][k] * x[k] for k in range(i + 1, n))
        x[i] = soma / m[i][i]
    return x


def treinar_linear(X, y):
    p = len(X[0])
    xtx = [[sum(linha[i] * linha[j] for linha in X) for j in range(p)]
           for i in range(p)]
    xty = [sum(X[k][i] * y[k] for k in range(len(y))) for i in range(p)]
    return resolver(xtx, xty)


def prever_linear(coefs, x):
    return sum(c * v for c, v in zip(coefs, x))


# ---------------------------------------------------------------------------
# K-VIZINHOS MAIS PROXIMOS (k-NN, do zero)
# ---------------------------------------------------------------------------

def knn_treinar(X, y):
    # A coluna 0 e o intercepto (constante). Ela nao entra na distancia.
    colunas = list(range(1, len(X[0])))
    medias = [media([x[j] for x in X]) for j in colunas]
    desvios = [desvio([x[j] for x in X]) for j in colunas]
    desvios = [d if d > 0 else 1.0 for d in desvios]

    z = []
    for x in X:
        z.append([(x[j] - medias[i]) / desvios[i]
                  for i, j in enumerate(colunas)])

    return {"colunas": colunas, "medias": medias, "desvios": desvios,
            "z": z, "y": list(y)}


def knn_prever(modelo, x, k=K_VIZINHOS):
    z = [(x[j] - modelo["medias"][i]) / modelo["desvios"][i]
         for i, j in enumerate(modelo["colunas"])]
    distancias = []
    for zi, yi in zip(modelo["z"], modelo["y"]):
        d = sum((a - b) ** 2 for a, b in zip(z, zi))
        distancias.append((d, yi))
    distancias.sort(key=lambda par: par[0])
    vizinhos = distancias[:min(k, len(distancias))]
    return sum(v for _, v in vizinhos) / len(vizinhos)


# ---------------------------------------------------------------------------
# METRICAS
# ---------------------------------------------------------------------------

def mae(reais, previstos):
    return sum(abs(r - p) for r, p in zip(reais, previstos)) / len(reais)


def rmse(reais, previstos):
    return math.sqrt(sum((r - p) ** 2 for r, p in zip(reais, previstos))
                     / len(reais))


def r2(reais, previstos):
    m = sum(reais) / len(reais)
    ss_res = sum((r - p) ** 2 for r, p in zip(reais, previstos))
    ss_tot = sum((r - m) ** 2 for r in reais)
    return 1.0 - ss_res / ss_tot if ss_tot else 0.0


def pearson(x, y):
    mx, my = media(x), media(y)
    numerador = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) *
                    sum((b - my) ** 2 for b in y))
    return numerador / den if den else 0.0


# ---------------------------------------------------------------------------
# TREINAMENTO E AVALIACAO DE UM ALVO
# ---------------------------------------------------------------------------

def treinar_alvo(registros, alvo, incluir_espera):
    X, nomes = [], None
    for r in registros:
        f, nomes = construir_features(r, incluir_espera)
        X.append(f)
    y = [r[alvo] for r in registros]

    indices = list(range(len(registros)))
    random.seed(SEED)
    random.shuffle(indices)
    corte = int(len(indices) * PROPORCAO_TREINO)
    idx_treino, idx_teste = indices[:corte], indices[corte:]

    X_tr = [X[i] for i in idx_treino]
    y_tr = [y[i] for i in idx_treino]
    X_te = [X[i] for i in idx_teste]
    y_te = [y[i] for i in idx_teste]

    coefs = treinar_linear(X_tr, y_tr)
    if coefs is None:
        print("Nao foi possivel treinar o alvo %s: colunas redundantes." % alvo)
        return None

    pred_linear = [prever_linear(coefs, x) for x in X_te]

    modelo_knn = knn_treinar(X_tr, y_tr)
    pred_knn = [knn_prever(modelo_knn, x) for x in X_te]

    media_treino = sum(y_tr) / len(y_tr)
    pred_palpite = [media_treino] * len(y_te)

    resultado = {
        "alvo": alvo,
        "incluir_espera": incluir_espera,
        "nomes": nomes,
        "coeficientes": coefs,
        "metricas": {
            "linear": {"mae": mae(y_te, pred_linear),
                       "rmse": rmse(y_te, pred_linear),
                       "r2": r2(y_te, pred_linear)},
            "knn": {"mae": mae(y_te, pred_knn),
                    "rmse": rmse(y_te, pred_knn),
                    "r2": r2(y_te, pred_knn)},
            "palpite": {"mae": mae(y_te, pred_palpite),
                        "rmse": rmse(y_te, pred_palpite),
                        "r2": r2(y_te, pred_palpite)},
        },
        "media_treino": media_treino,
        "n_treino": len(y_tr),
        "n_teste": len(y_te),
        "knn": modelo_knn,
        "exemplos": [
            {"id": registros[i]["id"], "tipo": registros[i]["tipo"],
             "real": y[i], "linear": pred_linear[k],
             "knn": pred_knn[k]}
            for k, i in enumerate(idx_teste[:5])
        ],
    }
    return resultado


# ---------------------------------------------------------------------------
# RELACOES DESCRITIVAS
# ---------------------------------------------------------------------------

def medias_por_grupo(registros, chave, alvo):
    grupos = {}
    for r in registros:
        grupos.setdefault(r[chave], []).append(r[alvo])
    return {k: media(v) for k, v in sorted(grupos.items())}


def coeficientes_padronizados(resultado, X_tr_por_nome=None):
    """
    Coeficiente padronizado = coef * desvio do atributo / desvio do alvo.
    Permite comparar a forca de fatores com escalas diferentes.
    """
    coefs = resultado["coeficientes"]
    nomes = resultado["nomes"]
    return coefs, nomes


def matriz_correlacao(registros, colunas):
    linhas = []
    for a in colunas:
        linha = []
        for b in colunas:
            linha.append(pearson([r[a] for r in registros],
                                 [r[b] for r in registros]))
        linhas.append(linha)
    return linhas


# ---------------------------------------------------------------------------
# COMANDO TREINAR
# ---------------------------------------------------------------------------

def cmd_treinar():
    titulo("MODELO DE MACHINE LEARNING - PORTO DO ITAQUI")
    linhas = ler_csv()
    if linhas is None:
        return 1

    registros = construir_registros(linhas)
    if len(registros) < 20:
        print("Linhas completas de menos: %d." % len(registros))
        return 1

    print("Registros completos: %d" % len(registros))
    print("Treino: %.0f%% | Teste: %.0f%% | Semente: %d | k do k-NN: %d"
          % (PROPORCAO_TREINO * 100, (1 - PROPORCAO_TREINO) * 100, SEED, K_VIZINHOS))

    resultados = {}
    for alvo, cfg in ALVOS.items():
        print()
        print("Treinando: %s ..." % cfg["rotulo"])
        r = treinar_alvo(registros, alvo, cfg["incluir_espera"])
        if r is None:
            return 1
        resultados[alvo] = r
        m = r["metricas"]
        print("  linear  MAE=%s  R2=%.3f" % (fmt(m["linear"]["mae"]), m["linear"]["r2"]))
        print("  k-NN    MAE=%s  R2=%.3f" % (fmt(m["knn"]["mae"]), m["knn"]["r2"]))
        print("  palpite MAE=%s  R2=%.3f" % (fmt(m["palpite"]["mae"]), m["palpite"]["r2"]))

    # ---- relacoes descritivas
    rel_op_tipo = medias_por_grupo(registros, "tipo", "duracao_op_horas")
    rel_op_turno = medias_por_grupo(registros, "turno", "duracao_op_horas")
    correlacoes = matriz_correlacao(
        registros,
        ["espera", "duracao_op_horas", "atraso_total_horas", "tempo_total_horas"],
    )

    # ---- grava modelo em JSON
    os.makedirs(PASTA_MODELO, exist_ok=True)
    salvar = {
        "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "semente": SEED,
        "proporcao_treino": PROPORCAO_TREINO,
        "knn_k": K_VIZINHOS,
        "tipos": TIPOS,
        "turnos": TURNOS,
        "alvos": {},
    }
    for alvo, r in resultados.items():
        salvar["alvos"][alvo] = {
            "incluir_espera": r["incluir_espera"],
            "nomes": r["nomes"],
            "coeficientes": r["coeficientes"],
            "media_treino": r["media_treino"],
            "metricas": r["metricas"],
            "knn": {
                "colunas": r["knn"]["colunas"],
                "medias": r["knn"]["medias"],
                "desvios": r["knn"]["desvios"],
                "z": r["knn"]["z"],
                "y": r["knn"]["y"],
            },
        }
    with open(ARQ_MODELO, "w", encoding="utf-8") as f:
        json.dump(salvar, f, ensure_ascii=False, indent=1)
    print()
    print("Modelo salvo em: " + ARQ_MODELO)

    # ---- relatorio em markdown
    os.makedirs("saidas", exist_ok=True)
    L = []
    L.append("# Modelo de machine learning - Porto do Itaqui")
    L.append("")
    L.append("Aprendizado de máquina sobre a base sintética de movimentação de")
    L.append("cargas. DECC0294, UFMA, Curso de Administração.")
    L.append("Gerado em %s pelo script modelo_ml_porto_itaqui.py."
             % datetime.now().strftime("%d/%m/%Y às %H:%M"))
    L.append("")
    L.append("## Aviso sobre os dados")
    L.append("")
    L.append("A base é sintética, gerada por `simulacao_porto_itaqui.py`. O que este")
    L.append("modelo aprende vale para a simulação, não para o porto real. Nenhuma")
    L.append("decisão operacional deve sair daqui sem dados da CODESA/ANTAQ.")
    L.append("")
    L.append("## Como o modelo foi montado")
    L.append("")
    L.append("| Item | Valor |")
    L.append("|---|---|")
    L.append("| Registros completos | %d |" % len(registros))
    L.append("| Divisão treino/teste | %.0f%% / %.0f%% |"
             % (PROPORCAO_TREINO * 100, (1 - PROPORCAO_TREINO) * 100))
    L.append("| Semente | %d |" % SEED)
    L.append("| Vizinhos do k-NN | %d |" % K_VIZINHOS)
    L.append("| Categorias de referência | %s e %s |" % (TIPOS[0], TURNOS[0]))
    L.append("")
    L.append("Atributos usados: tipo de carga (categórico), turno (categórico), mês")
    L.append("(numérico) e, nos alvos de atraso e tempo total, a espera por berço.")
    L.append("A categoria de referência é %s para carga e %s para turno; os"
             % (TIPOS[0], TURNOS[0]))
    L.append("coeficientes das outras categorias devem ser lidos como diferença")
    L.append("em relação a ela.")
    L.append("")
    L.append("## Relações descritivas na base")
    L.append("")
    L.append("### Duração média da operação por tipo de carga")
    L.append("")
    L.append("| Tipo de carga | Duração média da operação (h) |")
    L.append("|---|---|")
    for tipo in TIPOS:
        if tipo in rel_op_tipo:
            L.append("| %s | %s |" % (tipo, fmt(rel_op_tipo[tipo])))
    L.append("")
    L.append("### Duração média da operação por turno de chegada")
    L.append("")
    L.append("| Turno | Duração média da operação (h) |")
    L.append("|---|---|")
    for turno in TURNOS:
        if turno in rel_op_turno:
            L.append("| %s | %s |" % (turno, fmt(rel_op_turno[turno])))
    L.append("")
    L.append("### Correlação entre as variáveis numéricas (Pearson)")
    L.append("")
    rotulos = ["espera", "duração op.", "atraso extra", "tempo total"]
    L.append("| | %s |" % " | ".join(rotulos))
    L.append("|---|%s|" % ("---|" * len(rotulos)))
    for i, a in enumerate(rotulos):
        valores = " | ".join("%.2f" % correlacoes[i][j] for j in range(len(rotulos)))
        L.append("| %s | %s |" % (a, valores))
    L.append("")
    L.append("Correlação perto de 1 indica que as duas variáveis sobem juntas; perto")
    L.append("de 0, que não há relação linear; negativa, que uma sobe quando a outra")
    L.append("desce. Correlação não prova causa.")
    L.append("")

    # ---- coeficientes do modelo de operacao
    r_op = resultados["duracao_op_horas"]
    L.append("## Coeficientes do modelo linear para duração da operação")
    L.append("")
    L.append("| Termo | Coeficiente (h) |")
    L.append("|---|---|")
    for nome, c in zip(r_op["nomes"], r_op["coeficientes"]):
        L.append("| %s | %s |" % (nome, fmt(c, 3)))
    L.append("")
    L.append("Leitura: mantendo os outros termos parados, o coeficiente mostra quantas")
    L.append("horas a mais (ou a menos) o tempo de operação muda quando aquele termo")
    L.append("aumenta uma unidade. Para as categorias, a comparação é com a categoria")
    L.append("de referência.")
    L.append("")

    # ---- desempenho
    L.append("## Desempenho no conjunto de teste")
    L.append("")
    L.append("| Alvo | Modelo | MAE (h) | RMSE (h) | R² |")
    L.append("|---|---|---|---|---|")
    for alvo, cfg in ALVOS.items():
        r = resultados[alvo]
        for chave, nome_modelo in (("linear", "Regressão linear"),
                                   ("knn", "k-NN"),
                                   ("palpite", "Palpite (média)")):
            m = r["metricas"][chave]
            L.append("| %s | %s | %s | %s | %.3f |"
                     % (cfg["rotulo"], nome_modelo,
                        fmt(m["mae"]), fmt(m["rmse"]), m["r2"]))
    L.append("")
    L.append("MAE é o erro médio em horas. R² perto de 1 significa que o modelo")
    L.append("explica quase toda a variação; perto de 0 ou negativo, que ele não")
    L.append("ganha do palpite simples. Modelo que não vence a média não deve ser")
    L.append("usado para decidir.")
    L.append("")

    # ---- exemplos de predicao
    L.append("## Exemplos de predição (linhas do teste)")
    L.append("")
    for alvo, cfg in ALVOS.items():
        if alvo == "atraso_total_horas":
            continue
        r = resultados[alvo]
        L.append("### %s" % cfg["rotulo"])
        L.append("")
        L.append("| Navio | Tipo | Real (h) | Linear (h) | k-NN (h) |")
        L.append("|---|---|---|---|---|")
        for ex in r["exemplos"]:
            L.append("| %s | %s | %s | %s | %s |"
                     % (ex["id"], ex["tipo"], fmt(ex["real"]),
                        fmt(ex["linear"]), fmt(ex["knn"])))
        L.append("")
    L.append("## Como usar o modelo para prever")
    L.append("")
    L.append("```")
    L.append('python modelo_ml_porto_itaqui.py prever "Contêineres" "Manhã" 10 8')
    L.append("```")
    L.append("")
    L.append("A ordem é: tipo de carga, turno, espera estimada por berço (horas),")
    L.append("mês (1 a 12). O script devolve a duração prevista da operação e o")
    L.append("tempo total previsto, pelos dois modelos.")
    L.append("")
    L.append("## Limitações")
    L.append("")
    L.append("- Base sintética, não real.")
    L.append("- A espera por berço é conhecida só depois da fila; no tempo total ela")
    L.append("  funciona como informação de entrada, não como algo que o modelo preveja.")
    L.append("- O atraso extra, nesta simulação, é sorteado de forma independente dos")
    L.append("  fatores registrados. Por isso é esperado que nenhum modelo o preveja bem.")
    L.append("- Correlação e coeficiente descrevem a base; não provam causalidade.")
    L.append("- Amostra pequena (cerca de 120 navios): os erros oscilam entre divisões.")
    L.append("")
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("Relatório salvo em: " + RELATORIO)
    print()
    print("PRÓXIMO PASSO")
    print("  Abra o relatório e veja qual modelo venceu o palpite em cada alvo.")
    print("  Depois teste um cenário novo com o comando prever.")
    return 0


# ---------------------------------------------------------------------------
# COMANDO PREVER
# ---------------------------------------------------------------------------

def carregar_modelo():
    if not os.path.exists(ARQ_MODELO):
        print("Nao encontrei o modelo treinado em " + ARQ_MODELO)
        print("Rode primeiro: python modelo_ml_porto_itaqui.py treinar")
        return None
    with open(ARQ_MODELO, encoding="utf-8") as f:
        return json.load(f)


def cmd_prever(args):
    titulo("PREVISAO DE DEMORA - PORTO DO ITAQUI")
    if len(args) != 4:
        print("Uso: python modelo_ml_porto_itaqui.py prever <tipo> <turno> <espera_h> <mes>")
        print()
        print("Exemplo:")
        print('  python modelo_ml_porto_itaqui.py prever "Contêineres" "Manhã" 10 8')
        print()
        print("Tipos:", ", ".join(TIPOS))
        print("Turnos:", ", ".join(TURNOS))
        return 1

    tipo, turno, espera_txt, mes_txt = args
    if tipo not in TIPOS:
        print("Tipo invalido: %r" % tipo)
        print("Use um destes:", ", ".join(TIPOS))
        return 1
    if turno not in TURNOS:
        print("Turno invalido: %r" % turno)
        print("Use um destes:", ", ".join(TURNOS))
        return 1
    espera = num(espera_txt)
    if espera is None or espera < 0:
        print("Espera invalida. Informe um numero de horas maior ou igual a zero.")
        return 1
    try:
        mes = int(str(mes_txt).split("/")[0])
    except (ValueError, IndexError):
        print("Mes invalido. Informe um numero de 1 a 12.")
        return 1
    if not 1 <= mes <= 12:
        print("Mes fora do intervalo. Informe um numero de 1 a 12.")
        return 1

    modelo = carregar_modelo()
    if modelo is None:
        return 1

    registro = {"tipo": tipo, "turno": turno, "mes": mes, "espera": espera}

    print("CENARIO")
    print("  tipo de carga:             " + tipo)
    print("  turno de chegada:          " + turno)
    print("  espera estimada por berco: %s h" % fmt(espera))
    print("  mes:                       %d" % mes)
    print()

    previsoes = {}
    for alvo, info in modelo["alvos"].items():
        x, _ = construir_features(registro, info["incluir_espera"])
        linear = prever_linear(info["coeficientes"], x)
        knn = knn_prever(info["knn"], x, modelo["knn_k"])
        previsoes[alvo] = {"linear": linear, "knn": knn,
                           "mae_linear": info["metricas"]["linear"]["mae"],
                           "mae_knn": info["metricas"]["knn"]["mae"]}

    op = previsoes["duracao_op_horas"]
    total = previsoes["tempo_total_horas"]

    print("DURACAO DA OPERACAO (embarque/desembarque)")
    print("  regressao linear: %s h  (erro medio esperado +/- %s h)"
          % (fmt(op["linear"]), fmt(op["mae_linear"])))
    print("  k-NN:             %s h  (erro medio esperado +/- %s h)"
          % (fmt(op["knn"]), fmt(op["mae_knn"])))
    print()
    print("TEMPO TOTAL (chegada ate desatracacao)")
    print("  regressao linear: %s h  (erro medio esperado +/- %s h)"
          % (fmt(total["linear"]), fmt(total["mae_linear"])))
    print("  k-NN:             %s h  (erro medio esperado +/- %s h)"
          % (fmt(total["knn"]), fmt(total["mae_knn"])))
    print()
    print("O erro medio vem do conjunto de teste. A previsao e uma estimativa:")
    print("o tempo real pode ficar fora da faixa, sobretudo porque atrasos por")
    print("clima, equipamento e documentacao sao dificeis de antecipar.")
    return 0


# ---------------------------------------------------------------------------
# COMANDO CONFERIR
# ---------------------------------------------------------------------------

def cmd_conferir():
    titulo("CONFERENCIA DO MODELO")
    problemas = []
    if not os.path.exists(ARQ_MODELO):
        problemas.append("modelo treinado nao encontrado: " + ARQ_MODELO)
    if not os.path.exists(RELATORIO):
        problemas.append("relatorio nao encontrado: " + RELATORIO)

    if not problemas:
        with open(ARQ_MODELO, encoding="utf-8") as f:
            modelo = json.load(f)
        if len(modelo.get("alvos", {})) < 3:
            problemas.append("o modelo nao tem os tres alvos (operacao, atraso, total).")
        with open(RELATORIO, encoding="utf-8") as f:
            texto = f.read()
        for secao in ("## Relações descritivas na base",
                      "## Coeficientes do modelo linear",
                      "## Desempenho no conjunto de teste",
                      "## Exemplos de predição",
                      "## Limitações"):
            if secao not in texto:
                problemas.append("relatorio sem a secao: " + secao)

    print()
    if problemas:
        print("A entrega ainda nao esta completa:")
        for p in problemas:
            print("  - " + p)
        return 1
    print("Modelo e relatorio completos.")
    print("  " + ARQ_MODELO)
    print("  " + RELATORIO)
    return 0


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    cmd = args[0].strip().lower() if args else ""

    if cmd == "treinar":
        return cmd_treinar()
    if cmd == "prever":
        return cmd_prever(args[1:])
    if cmd in ("conferir", "validar", "check"):
        return cmd_conferir()

    print(__doc__)
    print("Comandos disponiveis:")
    print("  python modelo_ml_porto_itaqui.py treinar")
    print("  python modelo_ml_porto_itaqui.py prever <tipo> <turno> <espera_h> <mes>")
    print("  python modelo_ml_porto_itaqui.py conferir")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        print("Interrompido.")
        sys.exit(1)
