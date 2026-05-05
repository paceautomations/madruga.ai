---
title: "Business Vision"
updated: 2026-05-04
sidebar:
  order: 1
---
# ResenhAI — Business Vision

> Framework: Playing to Win (Lafley & Martin). Última atualização: 2026-05-04.

---

## 1. Tese & Aspiração

ResenhAI é a plataforma para comunidades de **esportes de areia** (futevôlei, beach tennis, vôlei de areia) que se organizam em grupos recorrentes. Onde os concorrentes resolvem ou torneio federado ou reserva de quadra, o ResenhAI cobre o ritual da **resenha** — registro de jogos, cálculo de stats e ranking persistente — e fecha o ciclo com cobrança automática, transformando o organizador em um sustentável "Dono da Resenha".

**Diferencial estrutural:** *efeito de rede ao nível do grupo* — cada novo membro adiciona dados ao ranking compartilhado, aumentando o valor para todos os outros — combinado com **marca construída na linguagem do esporte** ("Dono da Resenha", "Rei da Praia", badge 👑 visível no ranking público), gerando vínculo identitário que blinda contra cópia comoditizada de features.

**North Star Metric:** Grupos ativos pagantes.

| Horizonte | Grupos pagantes | MRR | NPS | Conversão cupom→pago |
|-----------|-----------------|-----|-----|----------------------|
| **6 meses** | 500 | R$ 15k | > 40 `[VALIDAR]` | > 60% no M4 |
| **12 meses (Dez/2026)** | **1.000** (meta firme) | ~R$ 40k `[DERIVAR]` | > 50 `[VALIDAR]` | — |
| **18 meses** | 2.000 | R$ 80k | > 50 | — |

---

## 2. Where to Play

### Mercado

- **TAM:** ~1,7 M praticantes BR — beach tennis 1,1 M (CBT 2023) + futevôlei 500 k (CBFV) + vôlei de areia recreativo ~100 k `[ESTIMAR]`.
- **SAM:** ~850 k praticantes engajados em arenas pagas / grupos recorrentes (filtro: ≥1×/semana). ~6.000 arenas operacionais BR `[ESTIMAR]` (CBFV declara >1.000 arenas de futevôlei; Total Beach Tennis lista milhares de quadras de BT; Ceará anunciou 501 novas arenas em 2024).
- **SOM 18m:** 2.000 grupos pagantes (~R$ 1 M ARR no cenário-base; até R$ 5,4 M ARR no cenário-stretch com upsell B2B). Crescimento puxado por: beach tennis +175 % entre 2021–2023 (CBT) e Brasil concentrando ~60 % dos jogadores mundiais.

### Cliente-alvo

| Dimensão | Detalhe |
|----------|---------|
| **Persona principal** | Organizador (Dono da Resenha) de grupo recorrente de 15–50 amigos |
| **Dor principal** | Organizar mensalidade + lista de presença + ranking dá trabalho manual; cobrar amigos é ainda pior |
| **Alternativa atual** | WhatsApp + planilha Google Sheets; ocasionalmente FutBora bot ou Copa Fácil para campeonato pontual |
| **Job-to-be-Done** | "Quero rodar minha resenha semanal sem virar contador, e ainda manter o pessoal animado pelo ranking" |

### Personas

| Persona | O que faz | O que ganha | Jornada principal |
|---------|-----------|-------------|-------------------|
| **Jogador** | Participa de 1+ grupos, registra jogos, vê stats próprias e ranking | Status no ranking, identidade ("badge 👑"), histórico de jogos | Recebe convite via WhatsApp → entra no grupo → joga → sobe no ranking |
| **Organizador (Dono da Resenha)** | Cria grupo, convida via WhatsApp, gerencia campeonatos, cobra mensalidade | Resenha sustentável e auto-financiada; tempo livre vs operação manual | Cria grupo → ativa cobrança → convida 20 amigos → cobra automático → mantém comunidade |
| **Quadra/Arena (Enterprise)** | Gerencia múltiplos grupos/turmas dentro da arena, dá visibilidade analítica para o dono | Operação dos grupos como serviço da arena, agregação de receita por turma | Tier Enterprise → multi-admin → integração com sistema da arena → branding próprio |
| **Professor (stakeholder)** | Coach autônomo em arena, recomenda app aos alunos, vira influenciador de adoção | Status, distribuição B2B2C, possível ferramenta para gerir suas próprias turmas | Adota como organizador → recomenda em aulas → vira canal de aquisição |

### Segmentos prioritários

1. **Organizadores de futevôlei (RJ/SP)** — engajamento social mais alto da categoria (@futevoleibrasil 400k, @ligafutevolei 78k). Ponto de partida do produto.
2. **Organizadores de beach tennis (nacional)** — maior volume de praticantes (1,1 M) e maior velocidade de crescimento (+175 %/2 anos). Próxima onda.
3. **Arenas (B2B Enterprise)** — adicionado depois do PMF do tier Organizador; canal de upsell para multi-grupo.

### Onde NÃO jogamos

- Apostas esportivas, jogos de azar, ou qualquer atividade ilegal/não ética.
- Reserva/booking de quadra (espaço de ArenaAi e Playtomic).
- Torneio federado eliminatório oficial (espaço de LetzPlay e CBT).
- Rede social geral (Instagram/TikTok cobrem; foco é a resenha, não o feed).
- Esportes fora do guarda-chuva "areia" (sem futsal, sem pickleball, sem padel) — pelo menos no horizonte 18m.

---

## 3. How to Win

### Moat estrutural: efeito de rede ao nível do grupo + marca

Cada novo membro que entra num grupo adiciona jogos ao histórico, partidas ao ranking compartilhado e dados às stats — o valor de **estar nesse grupo específico** cresce com o número de membros. Não é efeito de rede global como WhatsApp; é local, ao nível do grupo, e suficientemente forte para que o organizador (e os jogadores) não queiram migrar de plataforma e perder o ranking acumulado. É lock-in por **dado histórico**, não por contrato.

A segunda camada é a marca, construída na linguagem nativa do esporte: "Dono da Resenha", "Rei da Praia", badge 👑 exclusivo no ranking público do WhatsApp. Cada usuário com badge vira embaixador silencioso — o status é visível para todo o grupo. Marca + linguagem = ativo de longo prazo que reduz CAC e cria identidade emocional, dificultando que um concorrente bem-financiado ganhe traction só copiando feature por feature em ≤6 meses (cenário reconhecido como real pelo founder).

### Posicionamento

ResenhAI é "o app onde a resenha mora". Não competimos com torneio (LetzPlay), nem booking (ArenaAi), nem bracket eliminatório (Copa Fácil). Competimos com **WhatsApp + Google Sheets** — o substituto que mais grupos usam hoje — substituindo a planilha pelo ranking persistente, e o esforço manual de cobrança pelo Stripe nativo.

### Batalhas críticas

| # | Batalha | Métrica de sucesso | Por que importa |
|---|---------|--------------------|-----------------|
| 1 | Lançar cobrança Stripe ponta-a-ponta | Primeiro pagamento real até Q3/2026 | Sem cobrança, não há receita — bloqueia toda a tese |
| 2 | Atingir massa crítica de 500 grupos pagantes | 500 grupos no M6, com cupom FUTEVOLEIDEPRESSAO | Volume valida willingness-to-pay e gera dados para network effect |
| 3 | Ativar canais de distribuição via influenciadores de areia | CAC < R$ 30; ≥3 parcerias ativas em 6m | Comunidade de areia consome via influencer (@FutevoleiDepressao, @ligafutevolei); custo de mídia paga é proibitivo |
| 4 | Reduzir fricção de onboarding via WhatsApp | Tempo até criar primeiro grupo < 2 min | Atrito alto destrói network effect — cada novo membro precisa entrar fluido |
| 5 | Defender churn pós-cupom < 30 % em M4 | Pesquisa NPS + email sequence + push de upgrade | 80 % de cupom dobra churn (ProfitWell); estratégia v2 já mitigou para 50 %, mas precisa monitoração ativa |

---

## 4. Landscape

| Player | Foco | Preço entry | Cobre os 3 esportes de areia? |
|--------|------|-------------|-------------------------------|
| **Meu Ranking Organizador** | Ranking multi-esporte (raquete + areia) | Freemium `[VALIDAR]` | Sim — único concorrente direto multi-esporte |
| **LetzPlay (LPTennis)** | Torneio federado de tênis e beach tennis | Sob consulta `[FONTE?]` | Parcial (BT apenas) |
| **ArenaAi** | Gestão B2B de arena (reservas, alunos, financeiro) | Sob consulta `[FONTE?]` | Sim, mas no fluxo dono-da-quadra, não comunidade de jogadores |
| **Copa Fácil** | Gerenciador de campeonato eliminatório (genérico) | R$ 25–55/mês | Não — bracket, não rachão |
| **WhatsApp + Google Sheets + FutBora bot** | Substituto manual atual | Grátis | N/A — é o que substituímos |
| **ResenhAI** | Comunidade de areia + ranking + cobrança nativa | R$ 49,90/mês | **Sim** |

**Tese competitiva:** o espaço está vazio porque cada incumbente escolheu um lado do funil — torneio (LetzPlay/Ranking BT), booking (ArenaAi), bracket (Copa Fácil), ranking-só (Meu Ranking). Ninguém serve a comunidade **casual recorrente** (rachão semanal de 12-50 amigos) que paga mensalidade ao organizador. O substituto real é WhatsApp + planilha — sinal de que o problema vivido é "organizar e cobrar a minha resenha", não "rodar campeonato eliminatório". Há vácuo categórico para um especialista de comunidade-areia + cobrança nativa, e quem cravar a categoria primeiro trava o ranking de marca por 3–5 anos.

---

## 5. Riscos & Premissas

### Riscos

| # | Risco | Prob. | Impacto | Mitigação |
|---|-------|-------|---------|-----------|
| 1 | Cobrança ainda não está em produção (zero receita ativa) | Cert. | Alto | Stripe é épico #1 do roadmap; meta primeiro pagamento real Q3/2026 |
| 2 | Fragilidade da infra de automação que orquestra onboarding via WhatsApp | Média | Alto | Épico de consolidação da infra de automação (eliminar dependência da camada externa atual) |
| 3 | Churn pós-cupom de lançamento > 40 % em M4 | Alta | Alto | Onboarding forte M1-3, email sequence, cupom v2 reduzido para 50 % (ProfitWell: descontos > 30 % dobram churn) |
| 4 | Concorrente bem-financiado replica features em ≤ 6 meses (reconhecido como real pelo founder) | Média | Médio | Lock-in via dado histórico do grupo + marca/linguagem identitária + cobrança nativa em vez de feature isolada |
| 5 | Limite de 20 membros no tier inicial frustra organizadores em grupos médios (15–30 pessoas) | Média | Médio | Monitorar feedback; ajustar tier se >40 % dos grupos baterem o teto sem fazer upgrade |

### Premissas críticas

Se qualquer uma for falsa, a tese precisa ser revisada:

1. Organizadores de grupos recorrentes estão dispostos a pagar **R$ 49,90/mês** para liderar a resenha (validado teoricamente em pricing.md v2.0; falta validação com pagamento real).
2. *Network effect ao nível do grupo* cria lock-in suficiente para sustentar churn < 30 % após M6.
3. Distribuição via influenciadores de areia (Futevôlei Depressão, ligas regionais, professores de arena) é viável e mantém CAC < R$ 30.
4. Beach tennis continua a crescer ≥ 30 %/ano BR pelos próximos 18 meses (extrapolação otimista do +175 %/2 anos atual).
5. A migração do organizador de WhatsApp + planilha para ResenhAI **não exige refactor do hábito** — o ritual da resenha é preservado, só a operação muda.

---

## 6. Modelo de Negócio

### Pricing

| Tier | Preço/mês | Grupos | Membros/grupo | Características |
|------|-----------|--------|---------------|-----------------|
| **Jogador** | Grátis | 0 (participa) | — | Vê ranking, registra jogos, stats próprias |
| **Dono da Resenha** 🏐 | R$ 49,90 | 1 | 20 | Cria 1 grupo, 1 campeonato ativo, 5 análises AI/mês, histórico 6 meses |
| **Rei da Praia** 👑 ⭐ | R$ 79,90 | 3 | 50 | Badge 👑 exclusivo, AI ilimitado, histórico completo, acesso antecipado, Hall da Fama |
| **Enterprise (Arena)** | A negociar | Ilimitado | Ilimitado | Multi-admin, API access, branding customizado, suporte dedicado |

> Anual: 33 % de desconto. Cupom de lançamento `FUTEVOLEIDEPRESSAO` aplica 80 % off por 3 meses (limite 500 grupos). Cupom de influencer pós-lançamento: 50 % off por 2 meses.

### Vento estrutural

Beach tennis cresceu **+175 % entre 2021 e 2023** no Brasil (CBT) e o país concentra **~60 % dos jogadores mundiais**. Mercado em expansão acelerada, apoiado por programas estaduais (Ceará: 501 novas arenas em 2024). Quem cravar a categoria "comunidade de areia + cobrança nativa" trava o ranking de marca por 3–5 anos antes de a próxima onda de SaaS chegar.

### Unit economics

- **Custo variável:** ~R$ 5/mês/grupo (taxa Stripe + custo de infra + tokens de AI) `[VALIDAR]` após primeiros 100 grupos pagantes.
- **Margem bruta target:** 85 %.
- **Break-even por grupo:** instantâneo (R$ 49,90 − R$ 5 ≈ R$ 45 net).
- **CAC alvo:** < R$ 30 (canal influencer de areia).
- **Payback:** < 1 mês `[DERIVAR]`.

---

## 7. Linguagem Ubíqua

| Termo | Definição | Exemplo |
|-------|-----------|---------|
| **Resenha** | O encontro recorrente do grupo + a discussão que rola depois (jogo, ranking, zoações) | "Tem resenha sábado às 8" |
| **Grupo** | Comunidade fixa de jogadores que se reúnem regularmente — unidade básica do produto | "Esse é o grupo do Maracanã" |
| **Dono da Resenha** | Tier R$ 49,90 — organizador que cria e administra grupo, cobra mensalidade | "O dono da resenha é o João" |
| **Rei da Praia** | Tier premium R$ 79,90 — badge 👑 exclusivo visível no ranking | "O João é Rei da Praia" |
| **Ranking** | Lista persistente de jogadores no grupo, calculada a partir dos jogos registrados | "Vou subir no ranking sábado" |
| **Jogo** | Partida registrada no app — alimenta stats e ranking | "Adicionar jogo do Roni e Pedro" |
| **Stats** | Métricas individuais (winrate, química com dupla, sangue frio, rival saldo) | "Olha minha química com o Pedro" |
| **Esportes de areia** | Futevôlei + beach tennis + vôlei de areia — escopo do produto (futsal/padel/pickleball ficam fora) | "Plataforma de esportes de areia" |
| **Arena/Quadra** | Local físico de prática — possível tier Enterprise (B2B) | "A arena do Leblon" |
| **Professor** | Coach autônomo em arena — stakeholder secundário, possível canal de aquisição | "O professor recomendou o app" |
| **Convite** | Link ou token via WhatsApp que adiciona um novo membro a um grupo | "Manda o convite no zap" |

> Padronizar estes termos em todos os documentos, código e comunicação do projeto.
