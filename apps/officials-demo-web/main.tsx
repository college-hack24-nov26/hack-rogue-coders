import React from 'react';
import {createRoot} from 'react-dom/client';
import {Portal} from '../../packages/web-ui/Portal';
import '../../packages/web-ui/style.css';
createRoot(document.getElementById('root')!).render(<Portal mode="official"/>);
