/* Uygulamanin giris noktasi: React kokunu #kok elemanina baglar ve genel
   stilleri yukler. */

import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

createRoot(document.getElementById('kok')).render(
  <React.StrictMode><App /></React.StrictMode>,
)
