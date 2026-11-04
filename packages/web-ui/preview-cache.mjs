import {statSync} from 'node:fs';
import {resolve} from 'node:path';

export function previewBrowserCache() {
  return {
    name: 'jalsathi-preview-browser-cache',
    configurePreviewServer(server) {
      const assets = resolve(server.config.root, server.config.build.outDir, 'assets');
      server.middlewares.use((request, response, next) => {
        const path = (request.url ?? '').split('?')[0];
        const match = /^\/assets\/([\w.-]+-[\w-]{8,}\.(?:js|css))$/.exec(path);
        if (match && statSync(resolve(assets, match[1]), {throwIfNoEntry: false})?.isFile()) {
          response.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
        }
        next();
      });
    },
  };
}
