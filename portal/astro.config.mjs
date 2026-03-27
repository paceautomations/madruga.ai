// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import node from '@astrojs/node';
import mermaid from 'astro-mermaid';
import { LikeC4VitePlugin } from 'likec4/vite-plugin';

export default defineConfig({
  adapter: node({ mode: 'standalone' }),
  vite: {
    plugins: [
      LikeC4VitePlugin({
        workspace: '../platforms/fulano/model',
      }),
    ],
  },
  integrations: [
    starlight({
      title: 'Madruga-AI',
      customCss: ['./src/styles/custom.css'],
      components: {
        TableOfContents: './src/components/Empty.astro',
      },
      head: [
        { tag: 'script', attrs: { src: '/sidebar-toggle.js', defer: true } },
      ],
      sidebar: [
        {
          label: 'Fulano',
          items: [
            {
              label: 'Business',
              items: [
                { slug: 'fulano/business/vision' },
                { label: 'Business Process', link: '/fulano/business-flow/' },
                { slug: 'fulano/business/solution-overview' },
              ],
            },
            {
              label: 'Engineering',
              items: [
                { label: 'System Landscape', link: '/fulano/landscape/' },
                { label: 'Containers', link: '/fulano/containers/' },
                { slug: 'fulano/engineering/containers' },
                {
                  label: 'Context Map',
                  items: [
                    { label: 'Context Map', link: '/fulano/context-map/' },
                    { label: 'Channel', link: '/fulano/bc-channel/' },
                    { label: 'Conversation', link: '/fulano/bc-conversation/' },
                    { label: 'Safety', link: '/fulano/bc-safety/' },
                    { label: 'Operations', link: '/fulano/bc-operations/' },
                  ],
                },
                { slug: 'fulano/engineering/context-map' },
                { slug: 'fulano/engineering/domain-model' },
                { slug: 'fulano/engineering/integrations' },
              ],
            },
            {
              label: 'Planning',
              items: [
                { label: 'Roadmap', link: '/fulano/roadmap/' },
                {
                  label: 'Epics',
                  autogenerate: { directory: 'fulano/epics' },
                },
              ],
            },
            {
              label: 'ADRs',
              collapsed: true,
              items: [
                { label: 'Decision Overviews', link: '/fulano/decisions/' },
                { label: 'ADRs', autogenerate: { directory: 'fulano/decisions' } },
              ],
            },
            {
              label: 'Research',
              collapsed: true,
              autogenerate: { directory: 'fulano/research' },
            },
          ],
        },
      ],
    }),
    react(),
    mermaid(),
  ],
});
