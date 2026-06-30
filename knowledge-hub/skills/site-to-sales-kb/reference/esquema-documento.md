# Canonical document schema — site sales knowledge base

Copy this structure when compiling `00-knowledge-base.md`. Adapt section names to
the business, but keep the logical order. Every fact, price and condition must
carry its **source URL**. Use `_não disponível_` (or "_not available_") + the URL
you checked when a field is missing — never invent.

> Output language: match the site / the user's choice. Headers below are in
> Portuguese as the common case; translate them when the target language differs.

---

```markdown
# Base de conhecimento — <Nome da empresa>
_Fonte: <domínio> · Capturado em: <YYYY-MM-DD> · Foco: <vendas|suporte|ambos>_

## 1. Visão geral da empresa
- Quem é, história, números, missão/valores, diferenciais (USPs), taglines.
- Amostras de tom de voz (frases verbatim) para o bot imitar.
- Fonte(s): <url>

## 2. Catálogo de produtos / serviços
Para cada item (uma subseção ou linha de tabela):
- **Nome** · categorias em que aparece (entidade única, várias categorias)
- Descrição
- **Preço / condições** (à vista, parcelado, faixas) — _ou "não disponível"_
- Promoções, descontos, combos/kits, upsell/cross-sell
- CTA / caminho de conversão (link WhatsApp, comprar, orçamento, checkout)
- Quebra de objeção: garantia, troca/devolução/reembolso, prazos, FAQ
- Prova social: depoimentos, prêmios, avaliações
- Gatilhos de urgência/escassez (tempo limitado, sazonal)
- **Link de origem**

## 3. Localizações / unidades
Tabela: Unidade | Endereço | Telefone | WhatsApp | Horário | Link

## 4. Canal B2B / Corporativo
- Proposta, condições, formulário/contato, link. _(Omitir se não existir.)_

## 5. Franquias / parcerias
- Modelo, investimento, contato, link. _(Omitir se não existir.)_

## 6. Institucional / conteúdo de marca
- Sobre, blog, certificações, posicionamento.

## 7. Suporte ao cliente
- SAC, central de ajuda, FAQ (perguntas + respostas resumidas + link).

## 8. Políticas
- Pagamento · trocas/devoluções · privacidade · termos. Resumo + link de cada.

## 9. Contatos (tabela resumida)
Canal | Valor | Link

## 10. Redes sociais
Rede | Handle | Link

## 11. Notas para quem for treinar o bot
- Lacunas conhecidas (campos não disponíveis e onde se tentou buscar).
- Páginas que dependem de JavaScript e não puderam ser lidas.
- Divergências de contagem (capturado X de Y declarados pelo site).
- Recomendação de frequência de atualização.
```

---

## Mapping to Knowledge Hub wiki docs (when used in onboarding)

When the caller is the onboarding flow, split this single document into atomic
wiki docs:

| Schema section | Wiki doc | `read_full` |
|---|---|---|
| 1 (identity/USPs/tone) | overview + tone-of-voice | `true` |
| 1 (guardrails derived) | guardrails | `true` |
| 2 | catalog / pricing (one or more) | `false` |
| 3 | locations | `false` |
| 4–6 | B2B / institutional | `false` |
| 7–8 | support / policies | `false` |
| 9–10 | contacts | `false` |
| 11 | not a wiki doc — surface as gaps to the user | — |

Keep `read_full: true` rare and small; everything situational stays on-demand
via `read_when`.
