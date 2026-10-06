# Tutorial Básico de Markdown

Guia rápido com exemplos práticos para a disciplina DECC0294 - TIC Aplicada à Administração.

## 1. Títulos

Use `#` para títulos. Quanto mais `#`, menor o nível:

```markdown
# Título 1 - Nome do relatório
## Título 2 - Seção
### Título 3 - Subseção
```

Resultado:

# Título 1 - Nome do relatório
## Título 2 - Seção
### Título 3 - Subseção

## 2. Texto e ênfase

```markdown
Texto normal. **negrito**, *itálico*, ~~riscado~~.
Quebra de linha: deixe uma linha em branco entre parágrafos.
```

Resultado:

Texto normal. **negrito**, *itálico*, ~~riscado~~.

Quebra de linha: deixe uma linha em branco entre parágrafos.

## 3. Listas

Lista não ordenada:

```markdown
- Planejar
- Organizar
- Dirigir
- Controlar
```

- Planejar
- Organizar
- Dirigir
- Controlar

Lista ordenada:

```markdown
1. Levantar dados
2. Analisar dados
3. Tomar decisão
```

1. Levantar dados
2. Analisar dados
3. Tomar decisão

Lista de tarefas:

```markdown
- [x] Criar pasta entregas/
- [ ] Rodar atividade_modulo2.py
- [ ] Enviar entrega A1
```

- [x] Criar pasta entregas/
- [ ] Rodar atividade_modulo2.py
- [ ] Enviar entrega A1

## 4. Links e imagens

```markdown
[Slides do Módulo 1](modulo1-transformacao-digital.html)
![Gráfico de vendas](saidas/grafico.png)
```

Resultado: [Slides do Módulo 1](modulo1-transformacao-digital.html)

> Dica: no GitHub, link relativo abre o código-fonte do HTML. Use o GitHub Pages para ver o slide renderizado.

## 5. Citação

```markdown
> A quarta revolução industrial transforma a gestão. (SCHWAB, 2016)
```

> A quarta revolução industrial transforma a gestão. (SCHWAB, 2016)

## 6. Código

No texto: use crases. Exemplo: rode `python atividade_modulo1.py iniciar`.

Bloco de código:

````markdown
```python
print("Olá, Administração!")
```
````

Resultado:

```python
print("Olá, Administração!")
```

## 7. Tabelas

```markdown
| Entrega | Encontro | Peso |
|---|---|---|
| A1 | 3 | 40% da N1 |
| A2 | 6 | 60% da N1 |
```

| Entrega | Encontro | Peso |
|---|---|---|
| A1 | 3 | 40% da N1 |
| A2 | 6 | 60% da N1 |

## 8. Linha horizontal e nota

Três traços `---` criam uma linha:

---

## Exercício rápido

1. Crie um arquivo `minha-entrega.md`
2. Adicione um título, uma lista e uma tabela
3. Visualize no VS Code com `Ctrl+Shift+V`

Pronto. Com isso você já documenta entregas, relatórios e portfólio do projeto integrador.
