"use client"

import * as React from "react"
import { useTheme } from "next-themes"
import { Switch } from "@/components/ui/switch"
import { Moon, Sun} from "lucide-react"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  const handleThemeChange = () => {
    if (theme === "light") {
      setTheme("dark")
    } else if (theme === "dark") {
      setTheme("system")
    } else {
      setTheme("light")
    }
  }

  if (!mounted) {
    return (
      <Switch 
        disabled
        className="opacity-50"
      />
    )
  }

  const getCurrentThemeLabel = () => {
    switch (theme) {
      case "light": return <Sun className="h-4 w-4" />
      case "dark": return <Moon className="h-4 w-4" />
    }
  }

  return (
    <div className="flex items-center gap-2">
      <div className="text-muted-foreground">
        {getCurrentThemeLabel()}
      </div>
      <Switch
        checked={theme === "dark"}
        onCheckedChange={handleThemeChange}
        aria-label="Toggle theme"
      />
    </div>
  )
}