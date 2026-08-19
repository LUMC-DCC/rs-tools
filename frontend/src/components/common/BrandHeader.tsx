import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import lumcMonogram from '../../assets/lumc-monogram-blauw-png.png'
import ThemeSwitcher from './ThemeSwitcher'

export default function BrandHeader() {
  const [isScrolled, setIsScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 0)
    }

    handleScroll()

    window.addEventListener('scroll', handleScroll, { passive: true })

    return () => {
      window.removeEventListener('scroll', handleScroll)
    }
  }, [])

  return (
    <header className={`site-header ${isScrolled ? 'is-scrolled' : ''}`}>
      <Link className="brand" to="/" aria-label="Research Software Tools home">
        <span className="brand-mark" aria-hidden="true">
          <img src={lumcMonogram} alt="" />
        </span>
        <h2>Research Software Tools</h2>
      </Link>

      <ThemeSwitcher />
    </header>
  )
}