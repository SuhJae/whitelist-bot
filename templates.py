import nextcord


class MessageTemplates:
    @staticmethod
    def success(text: str) -> nextcord.Embed:
        return nextcord.Embed(title='', description='✅ ' + text, color=0x2B2D31)

    @staticmethod
    def error(text, footer: str = None) -> nextcord.Embed:
        embed = nextcord.Embed(title='', description='❌ ' + text, color=0x2B2D31)
        if footer:
            embed.set_footer(text=footer)
        return embed

