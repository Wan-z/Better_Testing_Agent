import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Landing from './components/Landing/Landing'
import Wizard from './components/Wizard/Wizard'
import About from './components/About/About'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/analyse" element={<Wizard />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </BrowserRouter>
  )
}
