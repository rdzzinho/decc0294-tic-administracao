#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  GERADOR DE PDF - Simulacao Porto do Itaqui
  Gera um PDF a partir do relatorio markdown e da base sintetica.
  Usa apenas a biblioteca padrao do Python (sem pip install).
=============================================================================
"""

import csv
import os


RELATORIO_MD = os.path.join("saidas", "relatorio_porto_itaqui.md")
BASE_CSV = os.path.join("dados", "porto_itaqui_movimentacao.csv")
PDF_SAIDA = os.path.join("saidas", "relatorio_porto_itaqui.pdf")

LARGURA_PAGINA = 595   # A4 em pontos (210 mm)
ALTURA_PAGINA = 842    # A4 em pontos (297 mm)
MARGEM = 50
LARGURA_TEXTO = LARGURA_PAGINA - 2 * MARGEM


def ler_relatorio_md(caminho):
    blocos = []
    with open(caminho, encoding="utf-8") as f:
        linhas = f.read().splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if linha.startswith("# "):
            blocos.append(("h1", linha[2:]))
        elif linha.startswith("## "):
            blocos.append(("h2", linha[3:]))
        elif linha.startswith("### "):
            blocos.append(("h3", linha[4:]))
        elif linha.startswith("|") and i + 1 < len(linhas) and linhas[i + 1].startswith("|"):
            tabela = []
            while i < len(linhas) and linhas[i].startswith("|"):
                tabela.append([c.strip() for c in linhas[i].strip("|").split("|")])
                i += 1
            blocos.append(("tabela", tabela))
            continue
        elif linha.startswith("- "):
            blocos.append(("bullet", linha[2:]))
        elif linha.strip() == "":
            blocos.append(("vazio", ""))
        else:
            blocos.append(("paragrafo", linha))
        i += 1
    return blocos


def ler_primeiras_linhas_csv(caminho, n=10):
    linhas = []
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        leitor = csv.reader(f, delimiter=";")
        for i, linha in enumerate(leitor):
            if i >= n:
                break
            linhas.append(linha)
    return linhas


def quebrar_texto(texto, largura_chars):
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if len(teste) <= largura_chars:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class GeradorPDF:
    def __init__(self, caminho):
        self.caminho = caminho
        self.objetos = []  # (id, bytes)
        self.next_id = 1
        self.id_fonte = None
        self.id_catalogo = None
        self.id_pages = None
        self.ids_paginas = []
        self.fluxo_atual = ""
        self.y = ALTURA_PAGINA - MARGEM - 40

    def novo_id(self):
        oid = self.next_id
        self.next_id += 1
        return oid

    def add_objeto(self, texto_str):
        oid = self.novo_id()
        self.objetos.append((oid, texto_str.encode("latin-1", "replace")))
        return oid

    def add_fluxo(self, texto_str):
        oid = self.novo_id()
        dados = texto_str.encode("latin-1", "replace")
        obj = b"<< /Length %d >>\nstream\n%s\nendstream\nendobj" % (len(dados), dados)
        self.objetos.append((oid, obj))
        return oid

    def _texto(self, x, y_, s, tamanho=12):
        self.fluxo_atual += (
            "BT /F1 %.2f Tf %.2f %.2f Td (%s) Tj ET\n"
            % (tamanho, x, y_, esc(s))
        )

    def _retangulo(self, x, y_, w, h, preencher=True):
        op = "f" if preencher else "S"
        self.fluxo_atual += "%.2f %.2f %.2f %.2f re %s\n" % (x, y_, w, h, op)

    def _linha(self, x1, y1, x2, y2):
        self.fluxo_atual += "%.2f %.2f m %.2f %.2f l S\n" % (x1, y1, x2, y2)

    def nova_pagina(self):
        # Fecha pagina anterior se houver
        if hasattr(self, "oid_pagina_atual"):
            self._finalizar_pagina()
        self.oid_pagina_atual = self.novo_id()
        self.oid_fluxo_atual = self.novo_id()
        self.oid_recursos_atual = self.novo_id()
        self.fluxo_atual = ""
        self.y = ALTURA_PAGINA - MARGEM - 40

    def _finalizar_pagina(self):
        id_recursos = self.add_objeto(
            "<< /Font << /F1 %d 0 R >> >>\nendobj" % self.id_fonte
        )
        id_fluxo = self.add_fluxo(self.fluxo_atual)
        id_pagina = self.oid_pagina_atual
        # Placeholder: o id real do objeto Pages ainda nao existe. Corrigido em salvar().
        self.objetos.append(
            (
                id_pagina,
                (
                    b"<< /Type /Page /Parent %d 0 R /Resources %d 0 R /Contents %d 0 R >>\nendobj"
                    % (0, id_recursos, id_fluxo)
                ).encode("latin-1", "replace"),
            )
        )
        self.ids_paginas.append(id_pagina)

    def espaco_necessario(self, espaco):
        if self.y < MARGEM + espaco:
            self._finalizar_pagina()
            self.nova_pagina()
            self.y = ALTURA_PAGINA - MARGEM - 40

    def salvar(self):
        # Fecha ultima pagina
        if hasattr(self, "oid_pagina_atual"):
            self._finalizar_pagina()

        # Criar objeto Pages (referencia as paginas)
        self.id_pages = self.add_objeto(
            "<< /Type /Pages /Kids [%s] /Count %d >>"
            % (" ".join("%d 0 R" % p for p in self.ids_paginas), len(self.ids_paginas))
        )

        # Agora corrigir os objetos de pagina para apontar para o id_pages
        # Reescrever objetos de pagina que ja foram adicionados
        novos_objetos = []
        for oid, dados in self.objetos:
            texto = dados.decode("latin-1", "replace")
            if texto.startswith("<< /Type /Page"):
                texto = texto.replace("/Parent %d 0 R" % 0, "/Parent %d 0 R" % self.id_pages)
                dados = texto.encode("latin-1", "replace")
            novos_objetos.append((oid, dados))
        self.objetos = novos_objetos

        # Catalogo
        self.id_catalogo = self.add_objeto(
            "<< /Type /Catalog /Pages %d 0 R >>" % self.id_pages
        )

        # Escrever arquivo
        with open(self.caminho, "wb") as f:
            f.write(b"%PDF-1.4\n")
            offsets = {}
            for oid, dados in self.objetos:
                offsets[oid] = f.tell()
                f.write(("%d 0 obj\n" % oid).encode("latin-1"))
                f.write(dados)
                f.write(b"\nendobj\n")
            xref_inicio = f.tell()
            f.write(b"xref\n0 %d\n" % (self.next_id))
            f.write(b"0000000000 65535 f \n")
            for oid in range(1, self.next_id):
                off = offsets.get(oid, 0)
                f.write(("%010d 00000 n \n" % off).encode("latin-1"))
            f.write(b"trailer\n<< /Size %d /Root %d 0 R >>\n" % (self.next_id, self.id_catalogo))
            f.write(b"startxref\n%d\n%%EOF\n" % xref_inicio)
        print("PDF gravado em: " + self.caminho)

    # ---------- operacoes de layout ----------

    def texto(self, s, tamanho=12, negrito=False):
        self._texto(MARGEM, self.y, s, tamanho)
        self.y -= 14 if tamanho >= 12 else 12

    def espaco(self, linhas=1):
        self.y -= 14 * linhas

    def linha_horizontal(self):
        self._linha(MARGEM, self.y, LARGURA_PAGINA - MARGEM, self.y)
        self.y -= 14


def gerar_pdf():
    if not os.path.exists(RELATORIO_MD):
        print("Nao encontrei " + RELATORIO_MD)
        print("Execute primeiro: simulacao_porto_itaqui.py analisar")
        return 1

    blocos = ler_relatorio_md(RELATORIO_MD)
    amostra_csv = ler_primeiras_linhas_csv(BASE_CSV, 8)

    pdf = GeradorPDF(PDF_SAIDA)
    pdf.id_fonte = pdf.add_objeto(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )
    pdf.nova_pagina()

    # Cabecalho
    pdf._texto(MARGEM, pdf.y, "Relatorio de Simulacao - Porto do Itaqui", tamanho=16)
    pdf.y -= 20
    pdf._texto(MARGEM, pdf.y, "Demora no embarque e desembarque de cargas - Dados sinteticos", tamanho=11)
    pdf.y -= 13
    pdf._texto(
        MARGEM, pdf.y,
        "DECC0294 - UFMA, Curso de Administracao. Gerado por simulacao_porto_itaqui.py",
        tamanho=9,
    )
    pdf.y -= 20
    pdf._linha(MARGEM, pdf.y, LARGURA_PAGINA - MARGEM, pdf.y)
    pdf.y -= 14

    altura_linha = 13

    for tipo, conteudo in blocos:
        if tipo == "h1":
            pdf.espaco_necessario(30)
            pdf._texto(MARGEM, pdf.y, conteudo, tamanho=15)
            pdf.y -= 20
        elif tipo == "h2":
            pdf.espaco_necessario(20)
            pdf._texto(MARGEM, pdf.y, conteudo, tamanho=13)
            pdf.y -= 17
        elif tipo == "h3":
            pdf.espaco_necessario(15)
            pdf._texto(MARGEM, pdf.y, conteudo, tamanho=12)
            pdf.y -= 14
        elif tipo == "paragrafo":
            pdf.espaco_necessario(30)
            for lin in quebrar_texto(conteudo, 110):
                pdf.espaco_necessario(15)
                pdf._texto(MARGEM, pdf.y, lin, tamanho=10)
                pdf.y -= 13
            pdf.y -= 4
        elif tipo == "bullet":
            pdf.espaco_necessario(15)
            pdf._texto(MARGEM, pdf.y, "- " + conteudo, tamanho=10)
            pdf.y -= 13
        elif tipo == "vazio":
            pdf.y -= 6
        elif tipo == "tabela":
            pdf.espaco_necessario(altura_linha * (len(conteudo) + 1))
            colunas = conteudo[0]
            ncol = len(colunas)
            # Cabecalho com fundo
            pdf._retangulo(MARGEM, pdf.y - altura_linha, LARGURA_TEXTO, altura_linha, preencher=True)
            pdf._texto(MARGEM + 4, pdf.y - altura_linha + 4, " | ".join(colunas), tamanho=8)
            pdf.y -= altura_linha
            for linha in conteudo[1:]:
                pdf.espaco_necessario(altura_linha)
                pdf._texto(MARGEM + 4, pdf.y - altura_linha + 4, " | ".join(linha), tamanho=8)
                pdf.y -= altura_linha
            pdf.y -= 6

    # Rodape: amostra CSV
    pdf.espaco_necessario(altura_linha * (len(amostra_csv) + 5))
    pdf._texto(MARGEM, pdf.y, "Amostra da base sintetica (dados/porto_itaqui_movimentacao.csv):", tamanho=11)
    pdf.y -= 17
    for linha in amostra_csv:
        pdf.espaco_necessario(altura_linha)
        pdf._texto(MARGEM, pdf.y - altura_linha + 4, " | ".join(linha)[:220], tamanho=7)
        pdf.y -= 13

    pdf.salvar()
    return 0


if __name__ == "__main__":
    import sys
    try:
        sys.exit(gerar_pdf())
    except BrokenPipeError:
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        print("Interrompido.")
        sys.exit(1)
