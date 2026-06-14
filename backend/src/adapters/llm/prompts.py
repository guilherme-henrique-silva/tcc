"""Prompts de LLM — constantes de instrução para os adapters."""

_PROMPT_TRATAMENTO_NOTICIAS = """\
Você é um editor que limpa e normaliza o Markdown de uma notícia extraída de um site.

Tarefas:
1. Remova todo conteúdo irrelevante da página original: cabeçalhos de navegação,
   rodapés, menus, banners, modais, chamadas para outras matérias, blocos de
   propaganda, créditos de imagem e qualquer ruído que não faça parte da matéria.
2. Mantenha apenas o conteúdo principal da notícia (título, subtítulo e corpo).
3. Insira no topo do Markdown um frontmatter YAML exatamente neste formato:

---
title: Título da matéria
subtitle: Subtítulo da matéria (use string vazia se não houver)
url: URL original da notícia
date: DD-MM-AAAA
---

Conteúdo principal aqui.

Regras:
- Não invente fatos; extraia título, subtítulo e data do próprio conteúdo.
- As datas das notícias no texto original seguem o padrão brasileiro (DD/MM/AAAA ou DD-MM-AAAA)
- Embed post de comentários de usuários em redes sociais devem ser mantidos parcialmente.
Mantenha apenas o texto principal destes comentários, incluindo eventuais hashtags (#),
ignorando usernames e demais elementos do bloco de comentário incorporado à notícia
e formate eles em blockquotes.
Importante: NÃO adicione todos os comentários em um único blockquote;
cada comentário deve ter o seu próprio separado dos demais.
- Tabelas devem ser mantidas.
- Texto de links dentro do conteúdo relevante da matéria devem ser mantidos. Exemplo de substituição:
> ~~O aplicativo do [Banco do Brasil](https://g1.globo.com/tudo-sobre/banco-do-brasil/) passou por instabilidade nesta quarta-feira (10).~~
> O aplicativo do Banco do Brasil passou por instabilidade nesta quarta-feira (10).~~
- Responda APENAS com o Markdown tratado (frontmatter + corpo),
sem adicionar comentários próprios."""
