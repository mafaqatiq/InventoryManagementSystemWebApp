"use client"

import * as React from "react"
import { Moon, Sun, Monitor } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const cycleTheme = () => {
    if (theme === "light") setTheme("dark")
    else if (theme === "dark") setTheme("system")
    else setTheme("light")
  }

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={cycleTheme}
      className="transition-colors hover:bg-gray-200 dark:hover:bg-gray-700"
    >
      <Sun className="h-[1.2rem] w-[1.2rem] transition-all scale-100 opacity-100 dark:scale-0 dark:opacity-0" />
      <Moon className="absolute h-[1.2rem] w-[1.2rem] transition-all scale-0 opacity-0 dark:scale-100 dark:opacity-100" />
      <Monitor className="absolute h-[1.2rem] w-[1.2rem] transition-all scale-0 opacity-0 [.system_&]:scale-100 [.system_&]:opacity-100" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}