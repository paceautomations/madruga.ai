// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import node from '@astrojs/node';
import mermaid from 'astro-mermaid';
import { LikeC4VitePlugin } from 'likec4/vite-plugin';
import { discoverPlatforms, buildSidebar } from './src/lib/platforms.mjs';

const platforms = discoverPlatforms();

export default defineConfig({
  adapter: node({ mode: 'standalone' }),
  vite: {
    resolve: { preserveSymlinks: true },
    plugins: [
      LikeC4VitePlugin({
        workspace: '../platforms',
      }),
    ],
  },
  integrations: [
    starlight({
      title: 'Madruga-AI',
      routeMiddleware: './src/routeData.ts',
      customCss: ['./src/styles/custom.css'],
      components: {
        Header: './src/components/CustomHeader.astro',
      },
      head: [
        { tag: 'script', attrs: { src: '/sidebar-toggle.js', defer: true } },
      ],
      sidebar: buildSidebar(platforms),
    }),
    react(),
    mermaid(),
  ],
});
