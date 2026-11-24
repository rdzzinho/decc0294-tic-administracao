#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  SIMULACAO DE DEMORA NO EMBARQUE E DESEMBARQUE DE CARGAS
  Porto do Itaqui - Sao Luis / MA
  Dados sinteticos (gerados por computador, com semente fixa para
  reprodutibilidade). Sem pip install, sem rede, sem modelo de linguagem.
=============================================================================

O QUE ESTE ARQUIVO E
    Um simulador de filas de atracacao e operacao de cargas. Ele gera uma
    base sintética de navios, simula a espera por berço, o tempo de
    operacao (embarque ou desembarque) e os atrasos por causa (clima,
    equipamento, mão de obra, documentacao), calcula estatisticas e grava
    saidas em dados/, saidas/ e entregas/.

COMO USAR (peca ao agente, no opencode desktop)

    1) execute simulacao_porto_itaqui.py
       Sem argumento, imprime estas instrucoes.

    2) execute simulacao_porto_itaqui.py gerar
       Gera a base sintetica em dados/porto_itaqui_movimentacao.csv
       (sempre a mesma, graças à semente fixa).

    3) execute simulacao_porto_itaqui.py analisar
       Calcula estatísticas descritivas e grava
       saidas/relatorio_porto_itaqui.md.

    4) execute simulacao_porto_itaqui.py graficos
       Gera saidas/grafico_porto_itaqui.html com graficos SVG puros.

    5) execute simulacao_porto_itaqui.py tudo
       Executa gerar + analisar + graficos em sequencia.

O QUE O SCRIPT NAO FAZ
    Nao usa dados reais do Porto do Itaqui. Os numeros sao inventados para
    exercicio de analise. Qualquer decisão operacional precisa de dados
    reais da CODESA/ANTAQ.

Nao precisa instalar nada. Roda com o Python que ja vem com o ambiente.
=============================================================================
"""

import csv
import math
import os
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CAMINHOS E CONSTANTES
# ---------------------------------------------------------------------------

BASE_DADOS = os.path.join("dados", "porto_itaqui_movimentacao.csv")
BASE_RELATORIO = os.path.join("saidas", "relatorio_porto_itaqui.md")
BASE_GRAFICOS = os.path.join("saidas", "grafico_porto_itaqui.html")

SEED = 202602  # semente fixa: reexecutar gera exatamente os mesmos números
random.seed(SEED)

DIAS_SIMULACAO = 90
NAVIOS_ESPERADOS = 140  # media alvo de navios no periodo
BERCOS = 4              # numero de berços do cais simulado

# Tipos de carga com tempo medio de operacao (horas) e desvio padrao
TIPOS_CARGA = {
    "Contêineres": {"media": 24, "dp": 6},
    "Granel sólido": {"media": 36, "dp": 10},
    "Granel líquido": {"media": 18, "dp": 5},
    "Carga geral": {"media": 48, "dp": 12},
}

# Fatores de atraso extra: (probabilidade, duracao media horas, dp horas)
FATORES_ATRASO = {
    "clima": (0.18, 8, 4),
    "equipamento": (0.12, 6, 3),
    "mao_de_obra": (0.10, 5, 2),
    "documentacao": (0.15, 4, 2),
}

TURNOS = ["Manhã", "Tarde", "Noite", "Madrugada"]

COLUNAS = [
    "id_navio", "tipo_carga", "data_chegada", "hora_chegada",
    "data_atracacao", "hora_atracacao", "data_inicio_op", "hora_inicio_op",
    "data_termino_op", "hora_termino_op", "data_desatracacao",
    "hora_desatracacao", "espera_berco_horas", "duracao_op_horas",
    "atraso_clima_horas", "atraso_equipamento_horas",
    "atraso_mao_de_obra_horas", "atraso_documentacao_horas",
    "tempo_total_horas", "atraso_total_horas", "turno", "mes",
]


# ---------------------------------------------------------------------------
# FUNCOES AUXILIARES
# ---------------------------------------------------------------------------

def titulo(t):
    print()
    print("=" * 74)
    print(" " + t)
    print("=" * 74)


def momento_aleatorio(dia_inicio):
    """Devolve um datetime aleatorio dentro do janela de simulacao."""
    segundos = random.random() * (DIAS_SIMULACAO * 24 * 3600)
    return dia_inicio + timedelta(seconds=segundos)


def tempo_servico(tipo_carga):
    """Tempo base de operacao (embarque/desembarque), em horas."""
    p = TIPOS_CARGA[tipo_carga]
    return max(2, random.gauss(p["media"], p["dp"]))


def fator_atraso():
    """Soma atrasos extras por causa, devolvendo um dicionario com cada um."""
    atrasos = {}
    total = 0.0
    for causa, (prob, media, dp) in FATORES_ATRASO.items():
        if random.random() < prob:
            v = max(0, random.gauss(media, dp))
        else:
            v = 0.0
        atrasos[causa] = round(v, 2)
        total += v
    return atrasos, round(total, 2)


def fmt_hora(dt):
    return dt.strftime("%d/%m/%Y %H:%M")


def fmt_data(dt):
    return dt.strftime("%d/%m/%Y")


def apenas_hora(dt):
    return dt.strftime("%H:%M")


def turno_do_dia(dt):
    h = dt.hour
    if 6 <= h < 12:
        return "Manhã"
    if 12 <= h < 18:
        return "Tarde"
    if 18 <= h < 0:
        return "Noite"
    return "Madrugada"


# ---------------------------------------------------------------------------
# 1. GERACAO DA BASE SINTETICA (simulacao de filas de atracacao)
# ---------------------------------------------------------------------------

def simular_fila():
    """Simulacao de eventos discretos simples com BERCOS cais e uma fila."""
    dia_inicio = datetime(2026, 8, 1, 0, 0, 0)

    # Gera chegadas com processo de Poisson (intervalos exponenciais)
    chegadas = []
    t = dia_inicio
    while True:
        intervalo = -math.log(1.0 - random.random()) * (
            (DIAS_SIMULACAO * 24) / NAVIOS_ESPERADOS
        )
        t = t + timedelta(hours=intervalo)
        if t > dia_inicio + timedelta(days=DIAS_SIMULACAO):
            break
        chegadas.append(t)

    # Limita ao volume esperado (caso o acaso gere muito fora ou pouco)
    if len(chegadas) > NAVIOS_ESPERADOS * 1.4:
        chegadas = sorted(chegadas)[: int(NAVIOS_ESPERADOS * 1.4)]

    navios = []
    bercos_livres = BERCOS
    fila = []  # lista de (navio, momento_chegada)
    proximo_id = 1

    # Ponteiro sobre as chegadas ordenadas
    chegada_idx = 0
    tempo_atual = dia_inicio

    # Fila de eventos: fim de operacao por berço (berço -> momento livre)
    berco_ate = {}  # id do berço -> momento em que fica livre

    while chegada_idx < len(chegadas) or fila or berco_ate:
        proxima_chegada = (
            chegadas[chegada_idx] if chegada_idx < len(chegadas) else None
        )

        # Proximo fim de operacao entre os berços ocupados
        proximo_fim = min(berco_ate.values()) if berco_ate else None

        # Decide qual evento processar primeiro
        if proximo_fim is not None and (
            proxima_chegada is None or proximo_fim <= proxima_chegada
        ):
            tempo_atual = proximo_fim
            # Libera berços que terminaram neste instante
            livres_agora = [b for b, ate in berco_ate.items() if ate <= tempo_atual]
            for b in livres_agora:
                del berco_ate[b]
                bercos_livres += 1
            continue

        # Processa chegada (pode ser mais de uma no mesmo instante)
        tempo_atual = proxima_chegada
        while (
            chegada_idx < len(chegadas)
            and chegadas[chegada_idx] <= tempo_atual + timedelta(seconds=1)
        ):
            chegada = chegadas[chegada_idx]
            tipo_carga = random.choice(list(TIPOS_CARGA.keys()))
            navios.append({
                "id": proximo_id,
                "tipo_carga": tipo_carga,
                "chegada": chegada,
            })
            proximo_id += 1
            chegada_idx += 1

        # Tenta atracar navios da fila e das chegadas recentes
        atendidos_nesta_rodada = True
        while atendidos_nesta_rodada and bercos_livres > 0:
            atendidos_nesta_rodada = False
            # Navios ja criados e ainda nao atracados, em ordem de chegada
            pendentes = [
                n for n in navios if n.get("atracacao") is None
            ]
            pendentes.sort(key=lambda n: n["chegada"])
            for n in pendentes:
                if bercos_livres <= 0:
                    break
                if n["chegada"] <= tempo_atual:
                    bercos_livres -= 1
                    id_berco = "Berço %d" % (len(berco_ate) + BERCOS - bercos_livres)
                    n["atracacao"] = tempo_atual
                    n["id_berco"] = id_berco

                    duracao = tempo_servico(n["tipo_carga"])
                    atrasos, atraso_total = fator_atraso()
                    duracao_com_atraso = duracao + atraso_total

                    n["inicio_op"] = tempo_atual
                    n["termino_op"] = tempo_atual + timedelta(hours=duracao_com_atraso)
                    n["desatracacao"] = n["termino_op"] + timedelta(hours=2)
                    n["duracao_op"] = round(duracao, 2)
                    n["atrasos"] = atrasos
                    n["atraso_total"] = atraso_total

                    berco_ate[id_berco] = n["termino_op"]
                    atendidos_nesta_rodada = True

    # Navios que ficaram na fila ate o fim da janela (ainda atracando ou esperando)
    for n in navios:
        if n.get("atracacao") is None:
            # Atracou no ultimo instante disponível (espera truncada pela janela)
            n["atracacao"] = dia_inicio + timedelta(days=DIAS_SIMULACAO)
            n["id_berco"] = "Berço (fila)"
            n["inicio_op"] = n["atracacao"]
            n["termino_op"] = n["atracacao"]
            n["desatracacao"] = n["atracacao"]
            n["duracao_op"] = 0
            n["atrasos"] = {c: 0 for c in FATORES_ATRASO}
            n["atraso_total"] = 0

    return navios


def gerar_csv():
    """Executa a simulacao e grava o CSV em dados/."""
    os.makedirs("dados", exist_ok=True)
    navios = simular_fila()

    linhas = []
    for n in navios:
        chegada = n["chegada"]
        atracacao = n["atracacao"]
        inicio_op = n["inicio_op"]
        termino_op = n["termino_op"]
        desatracacao = n["desatracacao"]

        espera = (atracacao - chegada).total_seconds() / 3600.0
        total = (desatracacao - chegada).total_seconds() / 3600.0

        linhas.append({
            "id_navio": "ITQ-%04d" % n["id"],
            "tipo_carga": n["tipo_carga"],
            "data_chegada": fmt_data(chegada),
            "hora_chegada": apenas_hora(chegada),
            "data_atracacao": fmt_data(atracacao),
            "hora_atracacao": apenas_hora(atracacao),
            "data_inicio_op": fmt_data(inicio_op),
            "hora_inicio_op": apenas_hora(inicio_op),
            "data_termino_op": fmt_data(termino_op),
            "hora_termino_op": apenas_hora(termino_op),
            "data_desatracacao": fmt_data(desatracacao),
            "hora_desatracacao": apenas_hora(desatracacao),
            "espera_berco_horas": round(max(0, espera), 2),
            "duracao_op_horas": n["duracao_op"],
            "atraso_clima_horas": n["atrasos"]["clima"],
            "atraso_equipamento_horas": n["atrasos"]["equipamento"],
            "atraso_mao_de_obra_horas": n["atrasos"]["mao_de_obra"],
            "atraso_documentacao_horas": n["atrasos"]["documentacao"],
            "tempo_total_horas": round(max(0, total), 2),
            "atraso_total_horas": n["atraso_total"],
            "turno": turno_do_dia(chegada),
            "mes": chegada.strftime("%m/%Y"),
        })

    with open(BASE_DADOS, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        for l in linhas:
            w.writerow(l)

    print("Navios simulados: %d" % len(linhas))
    print("Base gravada em: " + BASE_DADOS)
    return linhas


# ---------------------------------------------------------------------------
# 2. ANALISE ESTATISTICA
# ---------------------------------------------------------------------------

def ler_csv():
    if not os.path.exists(BASE_DADOS):
        print("Nao encontrei " + BASE_DADOS)
        print("Execute primeiro: simulacao_porto_itaqui.py gerar")
        return None
    with open(BASE_DADOS, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def numero(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def media(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def mediana(vals):
    vals = sorted([v for v in vals if v is not None])
    if not vals:
        return None
    m = len(vals)
    return vals[m // 2] if m % 2 else (vals[m // 2 - 1] + vals[m // 2]) / 2


def pct(vals, limite, operador="maior"):
    vals = [v for v in vals if v is not None]
    if not vals:
        return 0.0
    if operador == "maior":
        conta = sum(1 for v in vals if v > limite)
    else:
        conta = sum(1 for v in vals if v < limite)
    return 100.0 * conta / len(vals)


def agrupar_por(linhas, coluna):
    grupos = {}
    for l in linhas:
        grupos.setdefault(l[coluna], []).append(l)
    return grupos


def analisar():
    linhas = ler_csv()
    if linhas is None:
        return 1

    total_navios = len(linhas)
    esperas = [numero(l["espera_berco_horas"]) for l in linhas]
    operacoes = [numero(l["duracao_op_horas"]) for l in linhas]
    totais = [numero(l["tempo_total_horas"]) for l in linhas]
    atrasos_totais = [numero(l["atraso_total_horas"]) for l in linhas]

    atraso_clima = [numero(l["atraso_clima_horas"]) for l in linhas]
    atraso_equip = [numero(l["atraso_equipamento_horas"]) for l in linhas]
    atraso_mao = [numero(l["atraso_mao_de_obra_horas"]) for l in linhas]
    atraso_doc = [numero(l["atraso_documentacao_horas"]) for l in linhas]

    navios_com_atraso = sum(
        1 for l in linhas if numero(l["atraso_total_horas"]) > 0
    )
    pct_atraso = 100.0 * navios_com_atraso / total_navios

    por_tipo = agrupar_por(linhas, "tipo_carga")
    por_turno = agrupar_por(linhas, "turno")
    por_mes = agrupar_por(linhas, "mes")

    os.makedirs("saidas", exist_ok=True)
    L = []
    L.append("# Relatório de simulação - Porto do Itaqui")
    L.append("")
    L.append("Simulação de dados sintéticos de embarque e desembarque de cargas.")
    L.append("Porto do Itaqui - São Luís / MA. DECC0294, UFMA, Curso de Administração.")
    L.append("Gerado em %s pelo script simulacao_porto_itaqui.py."
             % datetime.now().strftime("%d/%m/%Y às %H:%M"))
    L.append("")
    L.append("## Aviso importante")
    L.append("")
    L.append("Esta base é sintética (inventada com semente aleatória fixa). Ela serve")
    L.append("apenas para exercício de análise de dados e visualização. Não use estes")
    L.append("números para decisões operacionais do porto real sem dados da CODESA/ANTAQ.")
    L.append("")
    L.append("## Visão geral da simulação")
    L.append("")
    L.append("| Indicador | Valor |")
    L.append("|---|---|")
    L.append("| Período simulado | %d dias (a partir de 01/08/2026) |" % DIAS_SIMULACAO)
    L.append("| Navios simulados | %d |" % total_navios)
    L.append("| Berços do cais simulado | %d |" % BERCOS)
    L.append("| Tempo médio de espera por berço | %s h |" % fmt_num(media(esperas)))
    L.append("| Mediana de espera por berço | %s h |" % fmt_num(mediana(esperas)))
    L.append("| Tempo médio de operação (embarque/desembarque) | %s h |" % fmt_num(media(operacoes)))
    L.append("| Tempo médio total (chegada → desatracação) | %s h |" % fmt_num(media(totais)))
    L.append("| Mediana do tempo total | %s h |" % fmt_num(mediana(totais)))
    L.append("| Navios com algum atraso extra | %d (%.1f%%) |" % (navios_com_atraso, pct_atraso))
    L.append("| Atraso total médio por navio | %s h |" % fmt_num(media(atrasos_totais)))
    L.append("| Navios que esperaram mais de 12 h por berço | %.1f%% |" % pct(esperas, 12))
    L.append("| Navios com operação acima de 48 h | %.1f%% |" % pct(operacoes, 48))
    L.append("")
    L.append("## Tempo total médio por tipo de carga")
    L.append("")
    L.append("| Tipo de carga | Navios | Espera média (h) | Operação média (h) | Tempo total médio (h) |")
    L.append("|---|---|---|---|---|")
    for tipo in sorted(por_tipo.keys()):
        grupo = por_tipo[tipo]
        e = media([numero(l["espera_berco_horas"]) for l in grupo])
        o = media([numero(l["duracao_op_horas"]) for l in grupo])
        t = media([numero(l["tempo_total_horas"]) for l in grupo])
        L.append("| %s | %d | %s | %s | %s |" % (tipo, len(grupo), fmt_num(e), fmt_num(o), fmt_num(t)))
    L.append("")
    L.append("## Atraso médio por causa (horas por navio)")
    L.append("")
    L.append("| Causa | Atraso médio (h) | Navios afetados |")
    L.append("|---|---|---|")
    causas = [
        ("Clima", atraso_clima),
        ("Equipamento", atraso_equip),
        ("Mão de obra", atraso_mao),
        ("Documentação", atraso_doc),
    ]
    for nome, vals in causas:
        afetados = sum(1 for v in vals if v and v > 0)
        L.append("| %s | %s | %d |" % (nome, fmt_num(media(vals)), afetados))
    L.append("")
    L.append("## Por turno de chegada")
    L.append("")
    L.append("| Turno | Navios | Tempo total médio (h) |")
    L.append("|---|---|---|")
    for turno in TURNOS:
        if turno in por_turno:
            grupo = por_turno[turno]
            t = media([numero(l["tempo_total_horas"]) for l in grupo])
            L.append("| %s | %d | %s |" % (turno, len(grupo), fmt_num(t)))
    L.append("")
    L.append("## Por mês")
    L.append("")
    L.append("| Mês | Navios | Tempo total médio (h) |")
    L.append("|---|---|---|")
    for mes in sorted(por_mes.keys()):
        grupo = por_mes[mes]
        t = media([numero(l["tempo_total_horas"]) for l in grupo])
        L.append("| %s | %d | %s |" % (mes, len(grupo), fmt_num(t)))
    L.append("")
    L.append("## Principais conclusões da simulação")
    L.append("")
    L.append("- O maior componente do tempo total tende a ser a operação em si (embarque/desembarque),")
    L.append("  não apenas a espera por berço.")
    L.append("- Tipo de carga influencia fortemente a duração: carga geral e granel sólido demoram mais.")
    L.append("- Aproximadamente %.1f%% dos navios tiveram algum atraso extra além do tempo planejado." % pct_atraso)
    L.append("- Clima e documentação são as causas de atraso mais frequentes nesta simulação.")
    L.append("")
    L.append("## Limitações")
    L.append("")
    L.append("- Dados sintéticos, não reais.")
    L.append("- Modelo de fila simplificado (berços fixos, sem prioridade de atracação).")
    L.append("- Não considera marés, calado dos navios, nem limitações de pilha no pátio.")
    L.append("")
    with open(BASE_RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print("Estatísticas gravadas em: " + BASE_RELATORIO)
    return 0


def fmt_num(v):
    if v is None:
        return "-"
    if abs(v - round(v)) < 1e-9:
        return "%d" % int(round(v))
    return "%.2f" % v


# ---------------------------------------------------------------------------
# 3. GRAFICOS SVG EM HTML
# ---------------------------------------------------------------------------

def svg_barras_horizontal(categorias, valores, titulo_grafico, largura=700, altura=300):
    """Gera um SVG de barras horizontais."""
    maxv = max(valores) if valores else 1
    partes = []
    partes.append('<svg width="%d" height="%d" xmlns="http://www.w3.org/2000/svg">' % (largura, altura))
    partes.append('<rect width="100%%" height="100%%" fill="#ffffff"/>')
    partes.append('<text x="10" y="24" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#4a1c3b">%s</text>' % titulo_grafico)
    altura_barra = (altura - 60) / len(categorias)
    for i, (cat, val) in enumerate(zip(categorias, valores)):
        y = 50 + i * altura_barra
        w = (val / maxv) * (largura - 260)
        partes.append('<rect x="240" y="%s" width="%s" height="%s" fill="#8e44ad" rx="2"/>' % (y, w, altura_barra - 8))
        partes.append('<text x="230" y="%s" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#4a1c3b">%s</text>' % (y + altura_barra / 2 + 4, cat))
        partes.append('<text x="%s" y="%s" font-family="Arial, sans-serif" font-size="12" fill="#4a1c3b">%s</text>' % (245 + w, y + altura_barra / 2 + 4, "%.2f h" % val))
    partes.append('</svg>')
    return "\n".join(partes)


def svg_barras_vertical(categorias, valores, titulo_grafico, largura=700, altura=350):
    """Gera um SVG de barras verticais."""
    maxv = max(valores) if valores else 1
    partes = []
    partes.append('<svg width="%d" height="%d" xmlns="http://www.w3.org/2000/svg">' % (largura, altura))
    partes.append('<rect width="100%%" height="100%%" fill="#ffffff"/>')
    partes.append('<text x="%d" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#4a1c3b">%s</text>' % (largura // 2, titulo_grafico))
    espaco = (largura - 100) / len(categorias)
    for i, (cat, val) in enumerate(zip(categorias, valores)):
        x = 60 + i * espaco
        h = (val / maxv) * (altura - 100)
        y = altura - 50 - h
        partes.append('<rect x="%s" y="%s" width="%s" height="%s" fill="#2e86c1" rx="2"/>' % (x + 15, y, espaco - 30, h))
        partes.append('<text x="%s" y="%s" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#4a1c3b">%s</text>' % (x + espaco / 2, altura - 35, cat[:14]))
        partes.append('<text x="%s" y="%s" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#2e86c1">%s</text>' % (x + espaco / 2, y - 6, "%.1f" % val))
    partes.append('<text x="40" y="%d" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#4a1c3b" transform="rotate(-90 40,%d)">Tempo (horas)</text>' % (altura // 2, altura // 2))
    partes.append('</svg>')
    return "\n".join(partes)


def gerar_graficos():
    linhas = ler_csv()
    if linhas is None:
        return 1

    por_tipo = agrupar_por(linhas, "tipo_carga")
    tipos = sorted(por_tipo.keys())
    totais_tipo = [media([numero(l["tempo_total_horas"]) for l in por_tipo[t]]) for t in tipos]
    esperas_tipo = [media([numero(l["espera_berco_horas"]) for l in por_tipo[t]]) for t in tipos]

    causas = ["Clima", "Equipamento", "Mão de obra", "Documentação"]
    vals_causas = [
        media([numero(l["atraso_clima_horas"]) for l in linhas]),
        media([numero(l["atraso_equipamento_horas"]) for l in linhas]),
        media([numero(l["atraso_mao_de_obra_horas"]) for l in linhas]),
        media([numero(l["atraso_documentacao_horas"]) for l in linhas]),
    ]

    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html lang='pt-BR'>")
    html.append("<head><meta charset='utf-8'><title>Gráficos - Porto do Itaqui</title></head>")
    html.append("<body style='font-family:Arial,sans-serif;max-width:900px;margin:40px auto;background:#f7f5fa;color:#333;'>")
    html.append("<h1 style='color:#4a1c3b;border-bottom:3px solid #c48ecc;padding-bottom:8px;'>Porto do Itaqui - Demora no embarque e desembarque de cargas</h1>")
    html.append("<p>Dados sintéticos gerados por simulação de filas. <a href='%s'>Ver base completa</a>.</p>" % BASE_DADOS)

    html.append("<h2 style='color:#4a1c3b;'>Tempo total médio por tipo de carga</h2>")
    html.append(svg_barras_horizontal(tipos, totais_tipo, "Tempo total médio por tipo de carga (horas)"))
    html.append("<p><small>Inclui espera por berço, operação e atrasos extras.</small></p>")

    html.append("<h2 style='color:#4a1c3b;'>Espera média por berço por tipo de carga</h2>")
    html.append(svg_barras_vertical(tipos, esperas_tipo, "Espera média por berço (horas)"))
    html.append("<p><small>Tempo que o navio aguarda na fila antes de atracar.</small></p>")

    html.append("<h2 style='color:#4a1c3b;'>Atraso médio por causa</h2>")
    html.append(svg_barras_vertical(causas, vals_causas, "Atraso médio por causa (horas por navio)"))
    html.append("<p><small>Tempo extra somado além do tempo planejado de operação.</small></p>")

    html.append("<h2 style='color:#4a1c3b;'>Relatório escrito</h2>")
    html.append("<p><a href='%s'>Abrir relatorio_porto_itaqui.md</a></p>" % BASE_RELATORIO)
    html.append("</body></html>")

    os.makedirs("saidas", exist_ok=True)
    with open(BASE_GRAFICOS, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

    print("Gráficos gravados em: " + BASE_GRAFICOS)
    return 0


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    args = [a.strip().lower() for a in __import__("sys").argv[1:]]
    cmd = args[0] if args else ""

    if cmd == "gerar":
        return gerar_csv()
    if cmd == "analisar":
        return analisar()
    if cmd == "graficos":
        return gerar_graficos()
    if cmd == "tudo":
        gerar_csv()
        analisar()
        gerar_graficos()
        print()
        print("Simulação completa finalizada.")
        return 0

    print(__doc__)
    print("Comandos disponíveis:")
    print("  python simulacao_porto_itaqui.py gerar      gera a base sintética em dados/")
    print("  python simulacao_porto_itaqui.py analisar   estatísticas em saidas/")
    print("  python simulacao_porto_itaqui.py graficos   gráficos SVG em saidas/")
    print("  python simulacao_porto_itaqui.py tudo       executa os três acima")
    return 0


if __name__ == "__main__":
    try:
        import sys
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        print("Interrompido.")
        sys.exit(1)
