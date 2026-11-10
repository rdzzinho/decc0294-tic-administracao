# -*- coding: utf-8 -*-
"""Reproducao do grafico 'Sales by region: 2009 to 2011'.

Valores extraidos da imagem original via OCR (Windows.Media.Ocr) e, onde
a leitura foi incerta, aproximados mantendo as tendencias descritas no
proprio grafico (Regiao A cai ~5% ao ano; Regioes D, E e F crescem).
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

anos = [2009, 2010, 2011]
dados = {
    'Region A': [3.8, 3.6, 3.4],
    'Region C': [3.5, 3.3, 3.1],
    'All Other': [2.4, 2.2, 2.1],
    'Region D': [1.0, 1.1, 1.4],
    'Region E': [0.8, 0.9, 1.1],
    'Region F': [0.6, 0.7, 0.8],
}
cores = {
    'Region A': '#1f4e79',
    'Region C': '#7f7f7f',
    'All Other': '#bfbfbf',
    'Region D': '#2e75b6',
    'Region E': '#548235',
    'Region F': '#c55a11',
}

fig, ax = plt.subplots(figsize=(7.38, 4.52))
for nome, vals in dados.items():
    ax.plot(anos, vals, marker='o', label=nome, color=cores[nome], linewidth=2)
    for x, y in zip(anos, vals):
        ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                    xytext=(0, 8), ha='center', fontsize=8)

ax.set_title('Sales by region: 2009 to 2011')
ax.set_ylabel('$USm')
ax.set_xticks(anos)
ax.set_ylim(0, 4.5)
ax.grid(True, axis='y', linestyle=':', alpha=0.5)
ax.legend(loc='upper left', fontsize=8, frameon=False)

fig.text(0.55, 0.22,
         'Sales in Region A decreased\n'
         'an average of 5% per year\n'
         'between 2009 and 2011.\n'
         'In contrast, sales in Regions\n'
         'D, E, and F increased during\n'
         'the same period.',
         fontsize=9)

fig.tight_layout()
fig.savefig('grafico_reproduzido.png', dpi=100)
print('Arquivo grafico_reproduzido.png gerado.')
PY