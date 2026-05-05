---
title: "Solution Overview"
updated: 2026-05-04
sidebar:
  order: 2
---
# ResenhAI — Solution Overview

## Visao de Solucao

Você abre o ResenhAI no celular antes de chegar na quadra. Vê quem confirmou presença na resenha de hoje, joga, registra cada partida em poucos segundos, e fecha com o ranking atualizado no grupo do WhatsApp — todo mundo vê quem subiu, quem caiu, quem é Rei da Praia daquele mês. Sua química com cada parceiro de dupla, seu sangue frio em pontos decisivos, sua presença na resenha — tudo vira identidade compartilhada com o grupo.

Se você é o Dono da Resenha, a operação some: a cobrança roda no automático, novos membros entram via convite no zap, campeonatos saem em três toques. Você lidera, não administra.

A plataforma cobre o ciclo completo de uma comunidade de esportes de areia: identidade do jogador, pertencimento ao grupo, jogos registrados, stats que viram conversa, e cobrança que sustenta tudo. Onde antes era WhatsApp + planilha, agora é um lugar só.

> Personas e jornadas detalhadas → ver [Vision](./vision/).

---

## Mapa de Features

> Catálogo de funcionalidades user-facing. Linguagem de negócio — o "o que" e o "por quê", não o "como". Cada feature carrega **Status** (✅ done · 🔄 em progresso · 📋 planejado · 🧪 beta), **Para quem** (end-user / tenant / admin / ops) e, quando aplicável, **Limites** observáveis.

### Identidade & Acesso

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Cadastro via WhatsApp** | ✅ done | end-user | Entra no app sem digitar senha — recebe código no zap, valida, está dentro |
| **Convite por link/token** | ✅ done | end-user + tenant | Dono da Resenha gera link, manda no grupo do zap, novos membros entram em 1 toque |
| **Perfil do jogador** | ✅ done | end-user | Foto, apelido, número WhatsApp, mão dominante e lado preferido na quadra (lado direito/esquerdo na dupla) |
| **Login multi-plataforma** | ✅ done | end-user | Mesma conta no iOS, Android e web — joga no celular, vê stats no notebook |

### Comunidade & Grupos

| Feature | Status | Para | Valor | Limites |
|---------|--------|------|-------|---------|
| **Criar grupo** | ✅ done | tenant | Dono cria grupo nomeado, adiciona quadra/local de referência e convida amigos | até 1 grupo no tier Dono / 3 grupos no tier Rei |
| **Gestão de membros** | ✅ done | tenant + admin | Adicionar, remover, promover a admin secundário, ver quem está ativo | até 20 membros (Dono) / 50 (Rei) |
| **Atualizações em tempo real** | ✅ done | end-user | Quando alguém confirma presença ou registra jogo, o grupo vê na hora — sem refresh manual | — |
| **Ranking público no WhatsApp** | ✅ done | end-user + tenant | Diariamente (Dono) ou diariamente + semanalmente (Rei), o app posta o ranking atualizado no grupo do zap — vira combustível da resenha | — |

### Operação de Jogo

| Feature | Status | Para | Valor | Limites |
|---------|--------|------|-------|---------|
| **Registrar jogo** | ✅ done | end-user | 4 toques — duplas, placar, salva. O ranking e os stats se atualizam automaticamente | — |
| **Criar campeonato** | ✅ done | tenant | Nome, formato, datas — campeonato fica visível pra todos do grupo | até 1 campeonato ativo (Dono) / 10 (Rei) |
| **Inscrever participantes** | ✅ done | tenant + end-user | Membros se inscrevem direto, dono confirma — fila clara, sem grupo paralelo | — |
| **Histórico de partidas** | ✅ done | end-user | Vê todos os seus jogos passados, com quem, quando, placar | últimos 6 meses (Dono) / completo (Rei) |

### Inteligência & Insights

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Ranking persistente do grupo** | ✅ done | end-user | Lista atualizada a cada jogo registrado — quem está em alta, quem caiu, quem é o Rei do mês |
| **Ranking por campeonato** | ✅ done | end-user + tenant | Tabela de classificação dedicada ao campeonato em curso |
| **Stats individuais** | ✅ done | end-user | Winrate, química com cada dupla, sangue frio em pontos decisivos, presença na resenha, saldo contra rival recorrente — vira identidade ("eu jogo bem com fulano") |
| **Análises com AI** | 📋 epic-stripe | end-user + tenant | Resumo natural da última semana, comparativo com mês anterior, sugestões de dupla — destrava com tier pago |
| **Badge 👑 no ranking** | 📋 epic-stripe | end-user | Selo visível no ranking público do WhatsApp para quem é Rei da Praia — status que todo mundo vê |
| **Hall da Fama** | 📋 epic-stripe | end-user + tenant | Histórico de campeões dos campeonatos do grupo — memória da comunidade |

### Cobrança & Monetização

| Feature | Status | Para | Valor | Limites |
|---------|--------|------|-------|---------|
| **Tier gratuito (Jogador)** | 📋 epic-stripe | end-user | Participa de grupos, registra jogos, vê ranking — 100% grátis pra sempre | não cria grupo |
| **Tier Dono da Resenha** | 📋 epic-stripe | tenant | Cria 1 grupo, cobra a galera, lidera a resenha | R$ 49,90/mês · até 20 membros · 1 campeonato ativo · histórico 6 meses |
| **Tier Rei da Praia** | 📋 epic-stripe | tenant | Múltiplos grupos, badge 👑, AI ilimitado, acesso antecipado a novidades | R$ 79,90/mês · até 50 membros/grupo · até 3 grupos · histórico completo |
| **Tier Enterprise (Arena)** | 📋 epic-stripe | tenant + admin | Multi-admin, branding próprio, integração com sistemas internos, suporte dedicado | preço a negociar |
| **Cupons de lançamento** | 📋 epic-stripe | tenant | `FUTEVOLEIDEPRESSAO` aplica 80% off por 3 meses (limite 500 grupos) — distribuição via influenciador de areia | válido até 500 grupos ou 3 meses |
| **Upgrade Dono → Rei** | 📋 epic-stripe | tenant | Quando o grupo bate o teto de 20 membros, o app oferece upgrade pro-rata em 2 toques | — |

---

## Proximos ciclos e visao de longo prazo

| Feature | Horizonte | Valor |
|---------|-----------|-------|
| **Cobrança ponta-a-ponta** | Próximo — epic-001-stripe | Liga monetização: tiers, cupons, enforcement de limites, upgrade flow — destrava receita ativa e desbloqueia o badge 👑 |
| **Automação WhatsApp consolidada** | Próximo — epic-002-edge-migration | Onboarding via zap deixa de depender de infra externa frágil; ganha estabilidade e velocidade pra escalar pra 2.000 grupos |
| **Observabilidade & qualidade da experiência** | Longo prazo | Painel de saúde do produto — onde a resenha trava, onde o convite falha, onde o ranking demora — pra agir antes do usuário reclamar |

---

## Principios de Produto

1. **WhatsApp-first** — onboarding, convite e ranking público vivem onde o usuário já vive; o app não compete com o zap, embarca nele.
2. **Mobile-first** — o produto roda no celular durante a resenha, com a quadra ali do lado; web é vitrine, não palco.
3. **Ranking persistente como motivador identitário** — status visível ("Rei da Praia", badge 👑, química com a dupla) é mais combustível do que estatística enterrada num dashboard.
4. **Free para participar, paga para liderar** — jogador é grátis pra sempre; quem cobra mensalidade da galera (Dono da Resenha) é quem remunera a operação.
5. **Comunidade é onde a resenha acontece** — privilegiamos o rachão recorrente sobre o torneio eliminatório; ranking persistente sobre bracket descartável.

---

## O que NAO fazemos

| NAO e... | Porque |
|----------|--------|
| **Casa de aposta ou jogo de azar** | Fora do escopo ético e legal — apostas no jogo da resenha não são parte do produto |
| **Sistema de booking de quadra** | Playtomic e ArenaAi cobrem reserva de horário; sobreposição mata diferenciação |
| **Plataforma de torneio federado** | LetzPlay e CBT cobrem inscrição em torneio oficial; o lock-in deles é regulatório, não produto |
| **Rede social geral (feed/timeline)** | Foco é a resenha, não o feed; o ranking é o nosso feed |
| **Multi-esporte universal** | Escopo é esportes de areia (futevôlei, beach tennis, vôlei de areia); futsal, padel e pickleball ficam fora no horizonte 18m |

---

> **Próximo passo:** `/madruga:business-process resenhai` — mapear fluxos core a partir do feature map priorizado.
