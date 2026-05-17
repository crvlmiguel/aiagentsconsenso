"""Identidade visual unificada da CONSENSO PLUS.

Todos os agentes do sistema (Maria, StayLocal, Tejo, Abby, agentes criados
no dashboard) partilham este tema base. A consistência visual é uma regra
de produto — alterações são feitas APENAS aqui e propagam automaticamente.

Exceções permitidas via dashboard: ajustes de contraste/acessibilidade
através do tab "Visual & Cores" — o utilizador pode customizar o tema
de um agente específico, mas o default fica sempre o tema CONSENSO.
"""

# Cores oficiais da marca CONSENSO PLUS
CONSENSO_BLUE = "#4591CE"      # Azul principal — header, CTA, bolha do user
CONSENSO_BLUE_DARK = "#2C6FA8"  # Azul escuro — gradiente do header, hover states
CONSENSO_BLUE_SOFT = "#E8F1F9"  # Azul suave — fundos de avatar, focus ring
CONSENSO_BLUE_BORDER = "#C7DDF0"  # Borda dos icebreakers e bolhas do bot
CONSENSO_GOLD = "#E4AC1E"        # Dourado — preços, badges, acentos do bot

# Tema unificado aplicado a TODOS os agentes seedados.
CONSENSO_THEME = {
    "primary": CONSENSO_BLUE,
    "primary_dark": CONSENSO_BLUE_DARK,
    "primary_soft": CONSENSO_BLUE_SOFT,
    "primary_border": CONSENSO_BLUE_BORDER,
    "bot": CONSENSO_GOLD,
}
