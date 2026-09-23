import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

// Leaflet's own CSS must load before any map mounts, or the tile <img> elements
// get no positioning rules and the whole basemap stacks into the top-left corner
// as a diagonal staircase. Importing it here rather than in IndiaMap keeps it out
// of the route-level render path.
import 'leaflet/dist/leaflet.css'

import './styles/base.css'
import './styles/components.css'
import './styles/tracking.css'
import './styles/photo.css'
import './styles/simulator.css'
import './styles/funds.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
