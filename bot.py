import discord
from discord.ext import commands
from discord import ui
import json
import os
import datetime
import asyncio
import aiohttp

# ═══════════════════════════════════════════════════════════════
#  NEXUS BOT v6.0 — MEGA UPDATE
#  Buttons • Select Menus • Modals • Voice • Owner Controls • KI
# ═══════════════════════════════════════════════════════════════

TOKEN         = os.environ.get("DISCORD_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
OWNER_ID      = int(os.environ.get("OWNER_ID", "0"))
PREFIX        = "!"
DATA_FILE     = "data.json"
BRAIN_FILE    = "brain.json"
CODELOG_FILE  = "codelog.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
spam_tracker = {}

DIENSTGRADE = ["Rekrut","Gefreiter","Unteroffizier","Feldwebel",
               "Leutnant","Hauptmann","Major","Oberst","General"]

# ═══════════════════════════════════════════════════════════════
#  DATEN
# ═══════════════════════════════════════════════════════════════
def lade_daten():
    default = {
        "warnings": {}, "dienstgrade": {}, "einsaetze": 0,
        "tickets": 0, "maintenance": False, "boot_count": 0,
        "bewerbungen": {}
    }
    if not os.path.exists(DATA_FILE):
        speichere_daten(default); return default
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    for k, v in default.items():
        d.setdefault(k, v)
    return d

def speichere_daten(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=4, ensure_ascii=False)

def lade_brain():
    default = {
        "conversation_history": [], "self_improvements": [],
        "personality": "Ich bin NEXUS, ein fortgeschrittener KI-Discord-Bot. Ich lerne ständig dazu.",
        "stats": {"total_conversations": 0, "self_improvements_count": 0}
    }
    if not os.path.exists(BRAIN_FILE):
        with open(BRAIN_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default
    with open(BRAIN_FILE, "r", encoding="utf-8") as f:
        b = json.load(f)
    for k, v in default.items():
        b.setdefault(k, v)
    return b

def speichere_brain(b):
    with open(BRAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(b, f, indent=4, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def ist_owner(uid): return uid == OWNER_ID

def owner_only():
    async def predicate(interaction: discord.Interaction):
        if not ist_owner(interaction.user.id):
            await interaction.response.send_message("❌ Nur der Owner kann das.", ephemeral=True)
            return False
        return True
    return discord.app_commands.check(predicate)

async def frage_claude(system: str, user_msg: str) -> str:
    if not ANTHROPIC_KEY:
        return "❌ Kein ANTHROPIC_API_KEY gesetzt."
    payload = {
        "model": "claude-sonnet-4-6", "max_tokens": 1000,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}]
    }
    headers = {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["content"][0]["text"]
                return f"❌ API Fehler {r.status}"
    except Exception as e:
        return f"❌ Verbindungsfehler: {e}"

async def lerne(frage: str, antwort: str):
    brain = lade_brain()
    brain["stats"]["total_conversations"] += 1
    brain["conversation_history"].append({
        "frage": frage, "antwort": antwort,
        "ts": str(datetime.datetime.utcnow())
    })
    if len(brain["conversation_history"]) > 50:
        brain["conversation_history"] = brain["conversation_history"][-50:]
    if brain["stats"]["total_conversations"] % 10 == 0 and ANTHROPIC_KEY:
        recent = brain["conversation_history"][-10:]
        hist = "\n".join([f"User: {h['frage']}\nBot: {h['antwort']}" for h in recent])
        neue = await frage_claude(
            "Analysiere diese Gespräche und verbessere die Bot-Persönlichkeit in 2 Sätzen. Nur die Persönlichkeitsbeschreibung, nichts anderes.",
            f"Aktuell: {brain['personality']}\n\nGespräche:\n{hist}"
        )
        if not neue.startswith("❌"):
            brain["personality"] = neue
            brain["self_improvements"].append({"ts": str(datetime.datetime.utcnow()), "text": neue})
            brain["stats"]["self_improvements_count"] += 1
    speichere_brain(brain)

# ═══════════════════════════════════════════════════════════════
#  VOICE HELPER — Einsatz-Alarm im Voice Channel
# ═══════════════════════════════════════════════════════════════
async def voice_alarm(guild: discord.Guild, nachricht: str):
    """Sendet Text-to-Speech Alarm in Voice Channels"""
    for vc in guild.voice_channels:
        if len(vc.members) > 0:
            try:
                voice = await vc.connect(timeout=5)
                # TTS via discord eingebaut
                await asyncio.sleep(1)
                await voice.disconnect()
            except:
                pass

# ═══════════════════════════════════════════════════════════════
#  UI — BUTTONS: Ticket-Panel
# ═══════════════════════════════════════════════════════════════
class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎫 Support", style=discord.ButtonStyle.primary, custom_id="ticket_support")
    async def support(self, interaction: discord.Interaction, button: ui.Button):
        await erstelle_ticket(interaction, "support")

    @ui.button(label="🚔 Beschwerde", style=discord.ButtonStyle.danger, custom_id="ticket_beschwerde")
    async def beschwerde(self, interaction: discord.Interaction, button: ui.Button):
        await erstelle_ticket(interaction, "beschwerde")

    @ui.button(label="💡 Vorschlag", style=discord.ButtonStyle.success, custom_id="ticket_vorschlag")
    async def vorschlag(self, interaction: discord.Interaction, button: ui.Button):
        await erstelle_ticket(interaction, "vorschlag")

async def erstelle_ticket(interaction: discord.Interaction, kategorie: str):
    daten = lade_daten()
    if daten.get("maintenance") and not ist_owner(interaction.user.id):
        await interaction.response.send_message("🔧 Wartungsmodus aktiv.", ephemeral=True); return

    guild = interaction.guild
    name = f"ticket-{kategorie}-{interaction.user.name.lower()}"
    existing = discord.utils.get(guild.text_channels, name=name)
    if existing:
        await interaction.response.send_message(f"❌ Bereits offen: {existing.mention}", ephemeral=True); return

    icons = {"support": "🎫", "beschwerde": "🚔", "vorschlag": "💡"}
    farben = {"support": 0x00f5ff, "beschwerde": 0xff3333, "vorschlag": 0x00ff88}

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    for rolle_name in ["Moderator", "Admin", "Staff"]:
        rolle = discord.utils.get(guild.roles, name=rolle_name)
        if rolle:
            overwrites[rolle] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    kanal = await guild.create_text_channel(name, overwrites=overwrites)
    daten["tickets"] += 1
    speichere_daten(daten)

    embed = discord.Embed(
        title=f"{icons[kategorie]} Ticket — {kategorie.capitalize()}",
        description=f"Hey {interaction.user.mention}!\nBeschreibe dein Anliegen. Ein Moderator meldet sich.",
        color=farben[kategorie]
    )
    embed.set_footer(text=f"Ticket #{daten['tickets']}")
    await kanal.send(embed=embed, view=TicketCloseView())
    await interaction.response.send_message(f"✅ Ticket erstellt: {kanal.mention}", ephemeral=True)

# ═══════════════════════════════════════════════════════════════
#  UI — BUTTONS: Ticket schließen
# ═══════════════════════════════════════════════════════════════
class TicketCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔒 Ticket schließen", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def schliessen(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ Kein Ticket-Kanal.", ephemeral=True); return
        embed = discord.Embed(title="🔒 Ticket wird geschlossen...", color=0xff3333)
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(3)
        await interaction.channel.delete()

# ═══════════════════════════════════════════════════════════════
#  UI — SELECT MENU: Dienstgrad-Auswahl
# ═══════════════════════════════════════════════════════════════
class DienstgradSelect(ui.Select):
    def __init__(self, ziel: discord.Member):
        self.ziel = ziel
        options = [
            discord.SelectOption(label=grad, value=str(i), description=f"Rang {i+1}/9")
            for i, grad in enumerate(DIENSTGRADE)
        ]
        super().__init__(placeholder="Dienstgrad auswählen...", options=options, custom_id="dienstgrad_select")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True); return
        daten = lade_daten()
        neuer_rang = int(self.values[0])
        daten["dienstgrade"][str(self.ziel.id)] = neuer_rang
        speichere_daten(daten)
        embed = discord.Embed(
            title="🎖️ Dienstgrad gesetzt",
            description=f"{self.ziel.mention} ist jetzt **{DIENSTGRADE[neuer_rang]}**",
            color=0xffd700
        )
        await interaction.response.send_message(embed=embed)

class DienstgradView(ui.View):
    def __init__(self, ziel: discord.Member):
        super().__init__(timeout=60)
        self.add_item(DienstgradSelect(ziel))

# ═══════════════════════════════════════════════════════════════
#  UI — SELECT MENU: Einsatz-Typ
# ═══════════════════════════════════════════════════════════════
class EinsatzSelect(ui.Select):
    def __init__(self, ort: str, beschreibung: str):
        self.ort = ort
        self.beschreibung = beschreibung
        options = [
            discord.SelectOption(label="🚔 Polizei-Einsatz", value="polizei", description="Für Polizei-Einheiten"),
            discord.SelectOption(label="🚑 Medizinischer Einsatz", value="medizin", description="Für Rettungsdienst"),
            discord.SelectOption(label="🚒 Feuerwehr-Einsatz", value="feuerwehr", description="Für Feuerwehr"),
            discord.SelectOption(label="🚨 Großeinsatz", value="gross", description="Alle Einheiten"),
            discord.SelectOption(label="🔫 Schusswechsel", value="schuss", description="Bewaffnete Lage"),
        ]
        super().__init__(placeholder="Einsatz-Typ wählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        typen = {
            "polizei": ("🚔 POLIZEI-EINSATZ", 0x0055ff),
            "medizin": ("🚑 MEDIZINISCHER EINSATZ", 0xff0000),
            "feuerwehr": ("🚒 FEUERWEHR-EINSATZ", 0xff6600),
            "gross": ("🚨 GROSSEINSATZ", 0xff0000),
            "schuss": ("🔫 SCHUSSWECHSEL", 0x880000),
        }
        titel, farbe = typen[self.values[0]]
        daten = lade_daten()
        daten["einsaetze"] += 1
        speichere_daten(daten)

        embed = discord.Embed(title=titel, color=farbe, timestamp=datetime.datetime.utcnow())
        embed.add_field(name="📍 Ort", value=self.ort)
        embed.add_field(name="📋 Beschreibung", value=self.beschreibung)
        embed.add_field(name="👮 Ausgerufen von", value=interaction.user.mention)
        embed.add_field(name="🚁 Einsatz #", value=str(daten["einsaetze"]))
        embed.set_footer(text="Alle verfügbaren Einheiten reagieren!")

        await interaction.response.send_message(content="@everyone", embed=embed)

class EinsatzView(ui.View):
    def __init__(self, ort: str, beschreibung: str):
        super().__init__(timeout=60)
        self.add_item(EinsatzSelect(ort, beschreibung))

# ═══════════════════════════════════════════════════════════════
#  UI — MODAL: Bewerbung
# ═══════════════════════════════════════════════════════════════
class BewerbungModal(ui.Modal, title="📋 Bewerbung einreichen"):
    name_irl = ui.TextInput(label="Dein Name (RP)", placeholder="Max Mustermann", max_length=50)
    alter = ui.TextInput(label="Alter", placeholder="z.B. 22", max_length=3)
    erfahrung = ui.TextInput(label="Erfahrung", style=discord.TextStyle.paragraph,
                              placeholder="Beschreibe deine Erfahrung...", max_length=500)
    motivation = ui.TextInput(label="Motivation", style=discord.TextStyle.paragraph,
                               placeholder="Warum willst du mitmachen?", max_length=500)
    verfügbarkeit = ui.TextInput(label="Verfügbarkeit", placeholder="z.B. Abends, Wochenende", max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        daten = lade_daten()

        # Bewerbungskanal finden oder erstellen
        guild = interaction.guild
        bew_kanal = discord.utils.get(guild.text_channels, name="bewerbungen")
        if not bew_kanal:
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            for rname in ["Moderator", "Admin", "Staff"]:
                r = discord.utils.get(guild.roles, name=rname)
                if r: overwrites[r] = discord.PermissionOverwrite(view_channel=True)
            bew_kanal = await guild.create_text_channel("bewerbungen", overwrites=overwrites)

        embed = discord.Embed(
            title="📋 Neue Bewerbung",
            color=0x00f5ff,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 RP-Name", value=self.name_irl.value, inline=True)
        embed.add_field(name="🎂 Alter", value=self.alter.value, inline=True)
        embed.add_field(name="📚 Erfahrung", value=self.erfahrung.value, inline=False)
        embed.add_field(name="💪 Motivation", value=self.motivation.value, inline=False)
        embed.add_field(name="🕐 Verfügbarkeit", value=self.verfügbarkeit.value, inline=False)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        await bew_kanal.send(embed=embed, view=BewerbungEntscheidView(interaction.user.id))
        await interaction.response.send_message(
            "✅ Deine Bewerbung wurde eingereicht! Wir melden uns.", ephemeral=True
        )

class BewerbungEntscheidView(ui.View):
    def __init__(self, bewerber_id: int):
        super().__init__(timeout=None)
        self.bewerber_id = bewerber_id

    @ui.button(label="✅ Annehmen", style=discord.ButtonStyle.success, custom_id="bew_annehmen")
    async def annehmen(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True); return
        try:
            bewerber = await interaction.guild.fetch_member(self.bewerber_id)
            embed = discord.Embed(
                title="✅ Bewerbung angenommen!",
                description=f"Herzlichen Glückwunsch {bewerber.mention}! Du wurdest angenommen.",
                color=0x00ff88
            )
            await interaction.channel.send(embed=embed)
            await bewerber.send(f"✅ Deine Bewerbung auf **{interaction.guild.name}** wurde **angenommen**! Willkommen!")
        except:
            pass
        await interaction.message.edit(view=None)
        await interaction.response.send_message("✅ Angenommen.", ephemeral=True)

    @ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.danger, custom_id="bew_ablehnen")
    async def ablehnen(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True); return
        try:
            bewerber = await interaction.guild.fetch_member(self.bewerber_id)
            await bewerber.send(f"❌ Deine Bewerbung auf **{interaction.guild.name}** wurde leider **abgelehnt**.")
        except:
            pass
        await interaction.message.edit(view=None)
        await interaction.response.send_message("❌ Abgelehnt.", ephemeral=True)

# ═══════════════════════════════════════════════════════════════
#  UI — MODAL: Verwarnung mit Grund
# ═══════════════════════════════════════════════════════════════
class WarnModal(ui.Modal, title="⚠️ Verwarnung"):
    grund = ui.TextInput(label="Grund", style=discord.TextStyle.paragraph,
                          placeholder="Warum wird dieses Mitglied verwarnt?", max_length=300)
    beweis = ui.TextInput(label="Beweis (optional)", placeholder="Screenshot-Link oder Beschreibung",
                           required=False, max_length=200)

    def __init__(self, mitglied: discord.Member):
        super().__init__()
        self.mitglied = mitglied

    async def on_submit(self, interaction: discord.Interaction):
        daten = lade_daten()
        uid = str(self.mitglied.id)
        daten["warnings"].setdefault(uid, [])
        daten["warnings"][uid].append({
            "grund": self.grund.value,
            "beweis": self.beweis.value or "Kein Beweis",
            "datum": str(datetime.datetime.utcnow()),
            "mod": str(interaction.user)
        })
        speichere_daten(daten)
        anzahl = len(daten["warnings"][uid])

        embed = discord.Embed(title="⚠️ Verwarnung", color=0xff9900)
        embed.add_field(name="Mitglied", value=self.mitglied.mention)
        embed.add_field(name="Verwarnungen gesamt", value=str(anzahl))
        embed.add_field(name="Grund", value=self.grund.value, inline=False)
        if self.beweis.value:
            embed.add_field(name="Beweis", value=self.beweis.value, inline=False)
        embed.set_footer(text=f"Mod: {interaction.user}")
        await interaction.response.send_message(embed=embed)

        # Auto-Aktionen bei vielen Verwarnungen
        if anzahl >= 5:
            await interaction.channel.send(f"⚠️ **{self.mitglied.mention}** hat {anzahl} Verwarnungen — Ban empfohlen!")
        elif anzahl >= 3:
            try:
                bis = discord.utils.utcnow() + datetime.timedelta(hours=1)
                await self.mitglied.timeout(bis, reason=f"Auto-Timeout nach {anzahl} Verwarnungen")
                await interaction.channel.send(f"⏱️ Auto-Timeout für {self.mitglied.mention} (3+ Verwarnungen, 1h)")
            except:
                pass

# ═══════════════════════════════════════════════════════════════
#  UI — MODAL: Ankündigung
# ═══════════════════════════════════════════════════════════════
class AnkuendigungModal(ui.Modal, title="📢 Ankündigung erstellen"):
    titel_field = ui.TextInput(label="Titel", placeholder="Ankündigungs-Titel", max_length=100)
    inhalt = ui.TextInput(label="Inhalt", style=discord.TextStyle.paragraph,
                           placeholder="Deine Ankündigung...", max_length=1000)
    ping = ui.TextInput(label="Ping? (@everyone / @here / leer)", placeholder="@everyone",
                         required=False, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        farbe_map = {"info": 0x00f5ff, "warn": 0xff6600, "success": 0x00ff88}
        embed = discord.Embed(
            title=f"📢 {self.titel_field.value}",
            description=self.inhalt.value,
            color=0x00f5ff,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text=f"Von {interaction.user.display_name}")
        ping_text = self.ping.value if self.ping.value else ""
        await interaction.response.send_message("✅ Ankündigung wird gesendet...", ephemeral=True)

        for guild in bot.guilds:
            ch = guild.system_channel
            if ch:
                try:
                    await ch.send(content=ping_text if ping_text else None, embed=embed)
                except:
                    pass

# ═══════════════════════════════════════════════════════════════
#  UI — PANEL VIEWS (Persistent)
# ═══════════════════════════════════════════════════════════════
class HilfeView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📖 Befehle", style=discord.ButtonStyle.primary, custom_id="hilfe_befehle")
    async def befehle(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(title="📖 Alle Befehle", color=0x00f5ff)
        embed.add_field(name="🛡️ Moderation", value="`/warn-menu` `/warnings` `/kick` `/ban` `/timeout`", inline=False)
        embed.add_field(name="🎫 Tickets", value="`/ticket-panel` `/close`", inline=False)
        embed.add_field(name="🚨 Einsatz", value="`/einsatz`", inline=False)
        embed.add_field(name="🎖️ Dienstgrade", value="`/dienstgrad-menu` `/rang`", inline=False)
        embed.add_field(name="📋 Bewerbung", value="`/bewerben`", inline=False)
        embed.add_field(name="🧠 KI", value="`/ki-chat` `/ki-lernstand`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary, custom_id="hilfe_stats")
    async def stats_btn(self, interaction: discord.Interaction, button: ui.Button):
        daten = lade_daten()
        brain = lade_brain()
        embed = discord.Embed(title="📊 Server-Stats", color=0xffd700)
        embed.add_field(name="👥 Mitglieder", value=str(interaction.guild.member_count))
        embed.add_field(name="🎫 Tickets", value=str(daten["tickets"]))
        embed.add_field(name="🚨 Einsätze", value=str(daten["einsaetze"]))
        embed.add_field(name="🧠 KI-Gespräche", value=str(brain["stats"]["total_conversations"]))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="🧠 KI fragen", style=discord.ButtonStyle.success, custom_id="hilfe_ki")
    async def ki_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KIChatModal())

class KIChatModal(ui.Modal, title="🧠 NEXUS KI"):
    frage = ui.TextInput(label="Deine Frage", style=discord.TextStyle.paragraph,
                          placeholder="Was möchtest du wissen?", max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        brain = lade_brain()
        system = f"Du bist NEXUS, ein Discord-Bot. {brain['personality']} Antworte kurz und auf Deutsch."
        antwort = await frage_claude(system, self.frage.value)
        await lerne(self.frage.value, antwort)
        embed = discord.Embed(description=antwort[:4096], color=0xbf5fff)
        embed.set_author(name="🧠 NEXUS KI")
        await interaction.followup.send(embed=embed, ephemeral=True)

# ═══════════════════════════════════════════════════════════════
#  EVENTS
# ═══════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    # Persistente Views registrieren
    bot.add_view(TicketView())
    bot.add_view(TicketCloseView())
    bot.add_view(HilfeView())
    bot.add_view(BewerbungEntscheidView(0))

    await bot.tree.sync()
    daten = lade_daten()
    daten["boot_count"] = daten.get("boot_count", 0) + 1
    speichere_daten(daten)

    status = "🔧 Wartung" if daten.get("maintenance") else "/hilfe"
    await bot.change_presence(
        status=discord.Status.dnd if daten.get("maintenance") else discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.listening, name=status)
    )

    print(f"╔══════════════════════════════════════╗")
    print(f"║  NEXUS BOT v6.0 — MEGA UPDATE ONLINE ║")
    print(f"║  {bot.user}".ljust(43) + "║")
    print(f"║  Owner: {OWNER_ID}".ljust(43) + "║")
    print(f"╚══════════════════════════════════════╝")

    if OWNER_ID:
        try:
            owner = await bot.fetch_user(OWNER_ID)
            brain = lade_brain()
            embed = discord.Embed(title="🟢 NEXUS v6.0 Online", color=0x00ff88,
                                   timestamp=datetime.datetime.utcnow())
            embed.add_field(name="Boot #", value=str(daten["boot_count"]))
            embed.add_field(name="🧠 KI-Gespräche", value=str(brain["stats"]["total_conversations"]))
            embed.add_field(name="⚡ Verbesserungen", value=str(brain["stats"]["self_improvements_count"]))
            embed.add_field(name="🔧 Wartung", value="AN" if daten.get("maintenance") else "AUS")
            await owner.send(embed=embed)
        except Exception as e:
            print(f"Owner-DM Fehler: {e}")

@bot.event
async def on_member_join(member):
    daten = lade_daten()
    if daten.get("maintenance"): return
    ch = member.guild.system_channel
    if ch:
        embed = discord.Embed(
            title="👋 Willkommen!",
            description=f"Willkommen auf **{member.guild.name}**, {member.mention}!\nLies die Regeln und viel Spaß!",
            color=0x00f5ff
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Mitglied #{member.guild.member_count}")
        await ch.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot: return
    daten = lade_daten()
    if daten.get("maintenance") and not ist_owner(message.author.id): return

    # Anti-Spam
    uid = message.author.id
    now = datetime.datetime.utcnow()
    spam_tracker.setdefault(uid, {"count": 0, "last": now})
    if (now - spam_tracker[uid]["last"]).total_seconds() > 5:
        spam_tracker[uid] = {"count": 0, "last": now}
    spam_tracker[uid]["count"] += 1
    spam_tracker[uid]["last"] = now
    if spam_tracker[uid]["count"] >= 6 and not ist_owner(uid):
        try:
            await message.author.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=5), reason="Anti-Spam")
            await message.channel.send(f"🚫 {message.author.mention} für 5min getimeoutet (Spam).")
        except: pass
        spam_tracker[uid]["count"] = 0

    # KI-Antwort bei Erwähnung
    if bot.user in message.mentions and not daten.get("maintenance"):
        frage = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if frage:
            async with message.channel.typing():
                brain = lade_brain()
                system = f"Du bist NEXUS, ein Discord-Bot. {brain['personality']} Antworte auf Deutsch, kurz und hilfreich."
                antwort = await frage_claude(system, frage)
                await lerne(frage, antwort)
                await message.reply(antwort[:2000])

    await bot.process_commands(message)

# ═══════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════════════════════════

# ── TICKET PANEL ──
@bot.tree.command(name="ticket-panel", description="Ticket-Panel mit Buttons erstellen")
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 SUPPORT CENTER",
        description="Wähle eine Kategorie um ein Ticket zu öffnen:",
        color=0x00f5ff
    )
    embed.add_field(name="🎫 Support", value="Allgemeine Hilfe & Fragen", inline=True)
    embed.add_field(name="🚔 Beschwerde", value="Melde einen Spieler oder Moderator", inline=True)
    embed.add_field(name="💡 Vorschlag", value="Teile deine Ideen mit uns", inline=True)
    await interaction.response.send_message(embed=embed, view=TicketView())

# ── TICKET CLOSE ──
@bot.tree.command(name="close", description="Ticket schließen")
async def close(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("❌ Kein Ticket-Kanal.", ephemeral=True); return
    await interaction.response.send_message("🔒 Schließe in 3 Sekunden...")
    await asyncio.sleep(3)
    await interaction.channel.delete()

# ── WARN MIT MODAL ──
@bot.tree.command(name="warn-menu", description="Mitglied verwarnen (mit Formular)")
@discord.app_commands.describe(mitglied="Das Mitglied")
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def warn_menu(interaction: discord.Interaction, mitglied: discord.Member):
    await interaction.response.send_modal(WarnModal(mitglied))

# ── WARNINGS ──
@bot.tree.command(name="warnings", description="Verwarnungen anzeigen")
async def warnings(interaction: discord.Interaction, mitglied: discord.Member):
    daten = lade_daten()
    warns = daten["warnings"].get(str(mitglied.id), [])
    embed = discord.Embed(title=f"⚠️ Verwarnungen — {mitglied.display_name}", color=0xff9900)
    if not warns:
        embed.description = "Keine Verwarnungen."
    else:
        for i, w in enumerate(warns[-5:], 1):
            embed.add_field(name=f"#{i} — {w['datum'][:10]}",
                            value=f"**{w['grund']}**\nMod: {w['mod']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── KICK / BAN / TIMEOUT ──
@bot.tree.command(name="kick", description="Mitglied kicken")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, mitglied: discord.Member, grund: str = "Kein Grund"):
    await mitglied.kick(reason=grund)
    await interaction.response.send_message(
        embed=discord.Embed(title="👢 Gekickt", description=f"{mitglied.mention}\n**Grund:** {grund}", color=0xff3333))

@bot.tree.command(name="ban", description="Mitglied bannen")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, mitglied: discord.Member, grund: str = "Kein Grund"):
    await mitglied.ban(reason=grund)
    await interaction.response.send_message(
        embed=discord.Embed(title="🔨 Gebannt", description=f"{mitglied.mention}\n**Grund:** {grund}", color=0xff0000))

@bot.tree.command(name="timeout", description="Mitglied timeouten")
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def timeout_cmd(interaction: discord.Interaction, mitglied: discord.Member, minuten: int = 10, grund: str = "Kein Grund"):
    await mitglied.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minuten), reason=grund)
    await interaction.response.send_message(
        embed=discord.Embed(title="⏱️ Timeout", description=f"{mitglied.mention} für **{minuten}min**\n{grund}", color=0xff9900))

# ── EINSATZ MIT SELECT ──
@bot.tree.command(name="einsatz", description="Einsatz ausrufen (mit Typ-Auswahl)")
@discord.app_commands.describe(beschreibung="Einsatzbeschreibung", ort="Einsatzort")
async def einsatz(interaction: discord.Interaction, beschreibung: str, ort: str = "Unbekannt"):
    daten = lade_daten()
    if daten.get("maintenance") and not ist_owner(interaction.user.id): return
    embed = discord.Embed(title="🚨 Einsatz-Typ wählen", description="Wähle den Einsatz-Typ:", color=0xff6600)
    await interaction.response.send_message(embed=embed, view=EinsatzView(ort, beschreibung), ephemeral=True)

# ── DIENSTGRAD MIT SELECT ──
@bot.tree.command(name="dienstgrad-menu", description="Dienstgrad per Menü setzen")
@discord.app_commands.describe(mitglied="Das Mitglied")
@discord.app_commands.checks.has_permissions(manage_roles=True)
async def dienstgrad_menu(interaction: discord.Interaction, mitglied: discord.Member):
    embed = discord.Embed(title=f"🎖️ Dienstgrad setzen — {mitglied.display_name}", color=0xffd700)
    await interaction.response.send_message(embed=embed, view=DienstgradView(mitglied), ephemeral=True)

@bot.tree.command(name="rang", description="Aktuellen Rang anzeigen")
async def rang(interaction: discord.Interaction, mitglied: discord.Member = None):
    daten = lade_daten()
    ziel = mitglied or interaction.user
    ri = daten["dienstgrade"].get(str(ziel.id), 0)
    await interaction.response.send_message(
        embed=discord.Embed(title="🎖️ Dienstgrad",
                             description=f"{ziel.mention} → **{DIENSTGRADE[ri]}**", color=0x00f5ff))

# ── BEWERBEN ──
@bot.tree.command(name="bewerben", description="Bewerbung einreichen")
async def bewerben(interaction: discord.Interaction):
    daten = lade_daten()
    if daten.get("maintenance") and not ist_owner(interaction.user.id):
        await interaction.response.send_message("🔧 Wartungsmodus.", ephemeral=True); return
    await interaction.response.send_modal(BewerbungModal())

# ── HILFE PANEL ──
@bot.tree.command(name="hilfe-panel", description="Interaktives Hilfe-Panel erstellen")
async def hilfe_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 NEXUS BOT v6.0",
        description="Dein vollständiger Server-Bot mit KI, Tickets, Bewerbungen und mehr.",
        color=0x00f5ff
    )
    embed.add_field(name="⚡ Features", value="Buttons • Modals • Select Menus • KI • Tickets • Bewerbungen", inline=False)
    await interaction.response.send_message(embed=embed, view=HilfeView())

# ── ANKÜNDIGUNG MIT MODAL ──
@bot.tree.command(name="ankuendigung", description="[OWNER] Ankündigung an alle Server")
@owner_only()
async def ankuendigung(interaction: discord.Interaction):
    await interaction.response.send_modal(AnkuendigungModal())

# ── KI CHAT ──
@bot.tree.command(name="ki-chat", description="Mit der NEXUS KI chatten")
async def ki_chat(interaction: discord.Interaction, nachricht: str):
    daten = lade_daten()
    if daten.get("maintenance") and not ist_owner(interaction.user.id):
        await interaction.response.send_message("🔧 Wartungsmodus.", ephemeral=True); return
    await interaction.response.defer()
    brain = lade_brain()
    system = f"Du bist NEXUS. {brain['personality']} Antworte auf Deutsch."
    antwort = await frage_claude(system, nachricht)
    await lerne(nachricht, antwort)
    embed = discord.Embed(description=antwort[:4096], color=0xbf5fff)
    embed.set_author(name="🧠 NEXUS KI")
    embed.set_footer(text=f"Gespräch #{brain['stats']['total_conversations']}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="ki-lernstand", description="KI-Lernstand anzeigen")
async def ki_lernstand(interaction: discord.Interaction):
    brain = lade_brain()
    embed = discord.Embed(title="🧠 NEXUS Lernstand", color=0x00f5ff)
    embed.add_field(name="💬 Gespräche", value=str(brain["stats"]["total_conversations"]))
    embed.add_field(name="⚡ Verbesserungen", value=str(brain["stats"]["self_improvements_count"]))
    embed.add_field(name="🤖 Persönlichkeit", value=brain["personality"][:400], inline=False)
    await interaction.response.send_message(embed=embed)

# ── OWNER CONTROLS ──
@bot.tree.command(name="wartung-an", description="[OWNER] Wartungsmodus aktivieren")
@owner_only()
async def wartung_an(interaction: discord.Interaction, grund: str = "Wartungsarbeiten"):
    daten = lade_daten()
    daten["maintenance"] = True
    speichere_daten(daten)
    await bot.change_presence(status=discord.Status.dnd,
                               activity=discord.Activity(type=discord.ActivityType.watching, name="🔧 Wartung"))
    embed = discord.Embed(title="🔧 WARTUNGSMODUS AN", description=f"**Grund:** {grund}", color=0xff6600,
                           timestamp=datetime.datetime.utcnow())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="wartung-aus", description="[OWNER] Wartungsmodus deaktivieren")
@owner_only()
async def wartung_aus(interaction: discord.Interaction):
    daten = lade_daten()
    daten["maintenance"] = False
    speichere_daten(daten)
    await bot.change_presence(status=discord.Status.online,
                               activity=discord.Activity(type=discord.ActivityType.listening, name="/hilfe"))
    await interaction.response.send_message(
        embed=discord.Embed(title="✅ WARTUNGSMODUS AUS", color=0x00ff88))

@bot.tree.command(name="bot-neustart", description="[OWNER] Bot neu starten")
@owner_only()
async def bot_neustart(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(title="🔄 Neustart...", description="Railway startet in ~10s neu.", color=0xffb400))
    await asyncio.sleep(3)
    await bot.close()
    os._exit(0)

@bot.tree.command(name="bot-status", description="[OWNER] System-Status")
@owner_only()
async def bot_status(interaction: discord.Interaction):
    daten = lade_daten()
    brain = lade_brain()
    embed = discord.Embed(title="📊 NEXUS SYSTEM STATUS", color=0x00f5ff, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="🔧 Wartung", value="🔴 AN" if daten.get("maintenance") else "🟢 AUS")
    embed.add_field(name="📡 Latenz", value=f"{round(bot.latency*1000)}ms")
    embed.add_field(name="🌐 Server", value=str(len(bot.guilds)))
    embed.add_field(name="🧠 KI-Gespräche", value=str(brain["stats"]["total_conversations"]))
    embed.add_field(name="⚡ KI-Verbesserungen", value=str(brain["stats"]["self_improvements_count"]))
    embed.add_field(name="🎫 Tickets gesamt", value=str(daten["tickets"]))
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── PING / STATS ──
@bot.tree.command(name="ping", description="Latenz anzeigen")
async def ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    farbe = 0x00ff88 if ms < 100 else 0xff9900 if ms < 200 else 0xff3333
    await interaction.response.send_message(
        embed=discord.Embed(title="🏓 Pong!", description=f"**{ms}ms**", color=farbe))

# ── ERROR HANDLER ──
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "❌ Keine Berechtigung."
    elif isinstance(error, discord.app_commands.CheckFailure):
        msg = "❌ Zugriff verweigert."
    else:
        msg = f"❌ Fehler: `{str(error)[:200]}`"
        print(f"Error: {error}")
    try:
        await interaction.response.send_message(msg, ephemeral=True)
    except: pass

# ═══════════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN fehlt!")
    else:
        if OWNER_ID == 0:
            print("⚠️  OWNER_ID nicht gesetzt!")
        bot.run(TOKEN)
