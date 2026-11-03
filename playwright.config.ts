import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/browser',timeout:60000,workers:1,use:{headless:true,launchOptions:{executablePath:process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'},screenshot:'only-on-failure'},webServer:[
{command:'uv run python -m scripts.e2e_server',url:'http://127.0.0.1:8011/health',reuseExistingServer:false,timeout:60000},
{command:'npx vite preview apps/admin-web --host localhost --port 5183',url:'http://localhost:5183',reuseExistingServer:false},
{command:'npx vite preview apps/officials-demo-web --host localhost --port 5184',url:'http://localhost:5184',reuseExistingServer:false},
{command:'uv run python -m http.server 8088 --bind localhost --directory apps/farmer-mobile/dist',url:'http://localhost:8088',reuseExistingServer:false}
]});
