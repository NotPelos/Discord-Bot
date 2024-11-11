import discord
from discord.ext import commands
from discord import Interaction, SelectOption, app_commands
from discord.ui import View, Select, Button, Modal, TextInput
import json
import os
import asyncio
import re
import aiofiles

# Cargar configuraciones
with open("secrets.json", "r", encoding="utf-8") as e:
    secrets = json.load(e)

# Configurar bot e intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Variables globales
tipo_sanciones = [{
    "name": "Aviso",
    "value": "Aviso"
}, {
    "name": "Disband",
    "value": "Disband"
}]
TOKEN = os.getenv('TOKEN', secrets['TOKEN'])
ID_Discord = [1202038662611882004,
              1264875034187661382]  # Lista de IDs de servidores
CHANNEL_ID = [1246201461722058752,
              1264881226213363754]  # Lista de IDs de canales de ventas
ChannelBand = [1259810202639663204,
               1264875034766344233]  # Lista de IDs de canales de bandas


# Funciones de utilidad
async def cargar_bandas(guild):
    bot_role = guild.get_member(bot.user.id).top_role
    roles = [
        role for role in guild.roles
        if role.position < bot_role.position and role != guild.default_role
    ]
    bandas = [{"name": role.name, "value": role.name} for role in roles]
    return bandas


async def send_or_update_bandas_select(guild, channel_ids):
    for channel_id in channel_ids:
        channel = guild.get_channel(channel_id)
        if not channel:
            print(
                f"Channel with ID {channel_id} not found in guild {guild.id}")
            continue

        bandas = await cargar_bandas(guild)
        if not bandas:
            print(f"No bands found for guild {guild.id}")
            continue

        print(
            f"Sending band selection to channel {channel_id} in guild {guild.id}"
        )
        view = BandasView(bandas)

        # Busca un mensaje existente con el select box para actualizarlo
        async for message in channel.history(limit=100):
            if message.author == bot.user and "Selecciona tu banda:" in message.content:
                await message.edit(content="Selecciona tu banda:", view=view)
                print(
                    f"Updated existing message in channel {channel_id} in guild {guild.id}"
                )
                return

        # Si no hay mensaje existente, envía uno nuevo
        await channel.send(content="Selecciona tu banda:", view=view)
        print(f"Sent new message to channel {channel_id} in guild {guild.id}")


async def send_or_update_ventas_message(guild, channel_ids):
    for channel_id in channel_ids:
        channel = guild.get_channel(channel_id)
        if not channel:
            print(
                f"Channel with ID {channel_id} not found in guild {guild.id}")
            continue

        message_text = "Pulsa en el botón para registrar tus ventas"
        ventas_view = VentaView()

        # Busca un mensaje existente con el botón de registro de ventas para actualizarlo
        async for message in channel.history(limit=100):
            if message.author == bot.user and message_text in message.content:
                await message.edit(content=message_text, view=ventas_view)
                print(
                    f"Updated existing ventas message in channel {channel_id} in guild {guild.id}"
                )
                return

        # Si no hay mensaje existente, envía uno nuevo
        await channel.send(content=message_text, view=ventas_view)
        print(
            f"Sent new ventas message to channel {channel_id} in guild {guild.id}"
        )


def es_admin():

    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator

    return discord.app_commands.check(predicate)


# Clase para el menú de selección
class BandasSelect(Select):

    def __init__(self, bandas):
        options = [
            SelectOption(label=banda["name"], value=banda["value"])
            for banda in bandas
        ]
        super().__init__(
            placeholder="Elige una banda...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: Interaction):
        role_name = self.values[0]
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"Rol '{role_name}' asignado correctamente.", ephemeral=True)
        else:
            await interaction.response.send_message("Rol no encontrado.",
                                                    ephemeral=True)


# Clase para la vista que contiene el Select
class BandasView(View):

    def __init__(self, bandas):
        super().__init__(timeout=None)
        self.add_item(BandasSelect(bandas))


# Clase para el formulario de ventas
class VentaModal(Modal):

    def __init__(self, title="Registrar Venta"):
        super().__init__(title=title)
        self.venta_para = TextInput(label="Venta para",
                                    placeholder="Nombre del comprador")
        self.articulos = TextInput(
            label="Artículos",
            placeholder=
            "Descripción del artículo 1\nDescripción del artículo 2\n...",
            style=discord.TextStyle.paragraph,
        )
        self.cantidades = TextInput(
            label="Cantidades",
            placeholder="Cantidad del artículo 1\nCantidad del artículo 2\n...",
            style=discord.TextStyle.paragraph,
        )
        self.precios = TextInput(
            label="Precios",
            placeholder=
            "Precio del artículo POR producto 1\nPrecio del artículo 2 POR \n...",
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.venta_para)
        self.add_item(self.articulos)
        self.add_item(self.cantidades)
        self.add_item(self.precios)

    async def on_submit(self, interaction: discord.Interaction):
        articulos = self.articulos.value.split("\n")
        cantidades = self.cantidades.value.split("\n")
        precios = self.precios.value.split("\n")

        articulos_vendidos = []
        total = 0.0

        for articulo, cantidad, precio in zip(articulos, cantidades, precios):
            cantidad = int(cantidad)
            precio = float(precio)
            subtotal = cantidad * precio
            total += subtotal
            articulos_vendidos.append(
                f"{articulo}: {cantidad} unidad(es) a ${precio:.2f} cada una")

        articulos_vendidos_text = "\n".join(articulos_vendidos)

        ventas_channel = None
        for role in interaction.user.roles:
            for channel in interaction.guild.text_channels:
                if ("ventas" in channel.name
                        and channel.permissions_for(role).read_messages):
                    ventas_channel = channel
                    break
            if ventas_channel:
                break

        if ventas_channel:
            embed = discord.Embed(title="Nueva Venta Registrada",
                                  color=discord.Colour.green())
            embed.add_field(name="Venta para",
                            value=self.venta_para.value,
                            inline=False)
            embed.add_field(name="Articulos vendidos",
                            value=articulos_vendidos_text,
                            inline=False)
            embed.add_field(name="Total", value=f"${total:.2f}", inline=False)
            await ventas_channel.send(embed=embed)
            await interaction.response.send_message(
                "Venta registrada exitosamente.",
                ephemeral=True,
                delete_after=5)
        else:
            await interaction.response.send_message(
                "No se pudo encontrar el canal de ventas correspondiente.",
                ephemeral=True,
            )


# Clase para la vista del botón de registro de ventas
class VentaView(View):

    def __init__(self):
        super().__init__(timeout=None)
        registrar_button = Button(label="Registrar Venta",
                                  style=discord.ButtonStyle.primary)
        registrar_button.callback = self.registrar_venta
        self.add_item(registrar_button)

    async def registrar_venta(self, interaction: Interaction):
        await interaction.response.send_modal(VentaModal())


# Manejo de errores de comandos de aplicación
@bot.event
async def on_app_command_error(interaction: discord.Interaction,
                               error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.errors.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send(
                "No tienes permiso para ejecutar este comando.",
                ephemeral=True)
        else:
            await interaction.response.send_message(
                "No tienes permiso para ejecutar este comando.",
                ephemeral=True)
    else:
        print(f"Un error ocurrió al ejecutar un comando: {error}")


# Evento on_ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Servers connected:")
    for guild in bot.guilds:
        print(f"{guild.name} (ID: {guild.id})")

    try:
        for guild_id in ID_Discord:
            guild = bot.get_guild(guild_id)
            if guild:
                print(f"Connected to guild: {guild.name} (ID: {guild.id})")
                await send_or_update_bandas_select(guild, ChannelBand)
                await send_or_update_ventas_message(guild, CHANNEL_ID)
                # Intentar sincronizar comandos
                try:
                    synced = await bot.tree.sync(guild=guild)
                    print(
                        f"Synced {len(synced)} commands successfully for guild {guild_id}"
                    )
                except discord.errors.Forbidden:
                    print(
                        f"Error: El bot no tiene permisos suficientes para sincronizar los comandos en guild {guild_id}."
                    )
                except discord.errors.HTTPException as e:
                    print(f"HTTPException Error in guild {guild_id}: {e}")
                print(
                    f"Comandos sincronizados correctamente en el servidor ID {guild_id}"
                )
            else:
                print(f"Guild with ID {guild_id} not found.")
    except Exception as e:
        print(f"Error durante la inicialización: {e}")


@bot.tree.command(name="sync", description="Sync commands with the server")
@es_admin()
async def sync_commands(interaction: discord.Interaction):
    try:
        synced = await bot.tree.sync(guild=interaction.guild)
        await interaction.response.send_message(
            f"Synced {len(synced)} commands successfully", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.response.send_message(
            "Error: No tengo permisos suficientes para sincronizar los comandos.",
            ephemeral=True)
    except discord.errors.HTTPException as e:
        await interaction.response.send_message(f"HTTPException Error: {e}",
                                                ephemeral=True)


# Comando para crear bandas
@bot.tree.command(
    name="crearbanda",
    description="Crea una banda con el nombre y el color especificados.",
)
@app_commands.describe(nombre="Nombre de la banda",
                       color_hex="Color en hexadecimal sin el #")
@es_admin()
async def crear_banda(interaction: discord.Interaction, nombre: str,
                      color_hex: str):
    print(
        f"Comando crearbanda ejecutado con nombre: {nombre} y color: {color_hex}"
    )

    # Validar el color hexadecimal
    if not re.fullmatch(r'^[0-9a-fA-F]{6}$', color_hex):
        await interaction.response.send_message(
            "El código de color proporcionado no es válido.",
            ephemeral=True,
            delete_after=5,
        )
        return

    try:
        color = discord.Colour(int(color_hex, 16))
    except ValueError:
        await interaction.response.send_message(
            "El código de color proporcionado no es válido.",
            ephemeral=True,
            delete_after=5,
        )
        return

    try:
        categoria = await interaction.guild.create_category(name=nombre)
        rol = await interaction.guild.create_role(name=nombre, color=color)

        overwrites = {
            interaction.guild.default_role:
            discord.PermissionOverwrite(read_messages=False),
            rol:
            discord.PermissionOverwrite(read_messages=True),
        }

        await categoria.create_text_channel(name="lideres-staff",
                                            overwrites=overwrites)
        await categoria.create_text_channel(name="entradas-salidas",
                                            overwrites=overwrites)
        await categoria.create_text_channel(name="ventas",
                                            overwrites=overwrites)
        await send_or_update_bandas_select(interaction.guild, ChannelBand)
        await interaction.response.send_message(
            f'Se ha creado la banda "{nombre}" con éxito y se han establecido los permisos.',
            ephemeral=True,
            delete_after=5,
        )
        print(f"Banda {nombre} creada con éxito.")
    except Exception as e:
        print(f"Error al crear banda: {e}")
        await interaction.response.send_message(
            "Ocurrió un error al crear la banda.",
            ephemeral=True,
            delete_after=5,
        )


# Autocompletar para bandas
async def autocompletar_bandas(interaction: discord.Interaction, current: str):
    roles = await interaction.guild.fetch_roles()
    bot_role = discord.utils.get(roles, name=bot.user.name)

    def is_below_bot(role):
        return role.position < bot_role.position and not role.permissions.administrator and role != interaction.guild.default_role

    filtered_roles = filter(is_below_bot, roles)

    return [
        app_commands.Choice(name=role.name, value=role.name)
        for role in filtered_roles if current.lower() in role.name.lower()
    ][:25]


# Comando para eliminar bandas
@bot.tree.command(
    name="eliminarbanda",
    description="Elimina una banda, el rol y expulsa a quienes tengan ese rol",
)
@app_commands.autocomplete(rol=autocompletar_bandas)
@es_admin()
async def eliminar_banda(interaction: discord.Interaction, rol: str):
    guild = interaction.guild
    categoria = discord.utils.get(interaction.guild.categories, name=rol)
    rol = discord.utils.get(interaction.guild.roles, name=rol)

    if categoria is None and rol is None:
        await interaction.response.send_message(
            f"No se encontró la banda o el rol con el nombre '{rol}'.",
            ephemeral=True,
            delete_after=5,
        )
        return

    if rol is not None:
        for member in list(guild.members):
            if len(member.roles) == 2 and rol in member.roles:
                try:
                    await member.kick(
                        reason=f"Eliminación de la banda {rol.name}")
                except discord.Forbidden:
                    await interaction.followup.send(
                        f"No se pudo expulsar a {member.display_name} debido a la falta de permisos.",
                        ephemeral=True,
                    )
                except discord.HTTPException as e:
                    await interaction.followup.send(
                        f"No se pudo expulsar a {member.display_name} debido a un error HTTP: {e}",
                        ephemeral=True,
                    )

    if categoria is not None:
        for canal in categoria.channels:
            await canal.delete()
        await categoria.delete()

    if rol is not None:
        await rol.delete()

    await send_or_update_bandas_select(interaction.guild, ChannelBand)

    try:
        with open("sanciones.json", "r+", encoding="utf-8") as file:
            sanciones = json.load(file)
            if rol.name in sanciones:
                del sanciones[rol.name]
                file.seek(0)
                json.dump(sanciones, file, indent=4, ensure_ascii=False)
                file.truncate()
    except FileNotFoundError:
        print("El archivo sanciones.json no fue encontrado.")
    except Exception as e:
        print(f"Error al actualizar sanciones.json: {e}")

    await interaction.response.send_message(
        f"Se ha eliminado la banda y rol '{rol.name}' con éxito.",
        ephemeral=True,
        delete_after=5,
    )


# Comando de anuncio
@bot.tree.command(
    name="anuncio",
    description=
    "Lanza un comunicado en el canal de comunicados mencionando a todos, utilizar \\n para saltos de linea",
)
@es_admin()
async def anuncio(interaction: discord.Interaction, *, titulo: str,
                  contenido: str):
    comunicados_channel = discord.utils.get(interaction.guild.text_channels,
                                            name="comunicados")

    if not comunicados_channel:
        await interaction.response.send_message(
            "El canal 'comunicados' no se encuentra en el servidor.",
            ephemeral=True,
            delete_after=5,
        )
        return

    contenido_formateado = contenido.replace("\\n", "\n")
    embed = discord.Embed(title=titulo,
                          description=contenido_formateado,
                          color=discord.Colour.blue())
    embed.set_footer(text="Grupo Oasis | Ilícito")

    try:
        await comunicados_channel.send(
            content="@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await interaction.response.send_message(
            "El anuncio ha sido publicado en 'comunicados'.",
            ephemeral=True,
            delete_after=5,
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "No tengo permisos para enviar mensajes en 'comunicados'.",
            ephemeral=True,
            delete_after=5,
        )
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"Ocurrió un error al enviar el mensaje: {e}",
            ephemeral=True,
            delete_after=5,
        )


# Comando para sancionar
@bot.tree.command(
    name="sancion",
    description="Comando para comunicar una sancion a un usuario.")
@es_admin()
@app_commands.describe(
    tipo="Elige entre Aviso o Disband.",
    banda="Nombre de las bandas de la lista",
    motivo="Detalles de la sanción.",
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Aviso", value="Aviso"),
    app_commands.Choice(name="Disband", value="Disband")
], )
@app_commands.autocomplete(banda=autocompletar_bandas)
async def sancion(interaction: discord.Interaction, tipo: str, banda: str,
                  motivo: str):
    sanciones_channel = discord.utils.get(interaction.guild.text_channels,
                                          name="sanciones")
    if sanciones_channel is None:
        await interaction.response.send_message(
            "El canal 'sanciones' no existe.", ephemeral=True, delete_after=5)
        return

    if tipo == "Aviso":
        embed = discord.Embed(
            title="**Aviso**",
            description=f"Se ha hablado con la {banda} por: {motivo}",
            color=discord.Colour.orange(),
        )
        # Incrementar contador de avisos
        with open("sanciones.json", "r+", encoding="utf-8") as file:
            sanciones = json.load(file)
            if banda not in sanciones:
                sanciones[banda] = {"Aviso": 0}
            sanciones[banda]["Aviso"] += 1
            file.seek(0)
            json.dump(sanciones, file, indent=4, ensure_ascii=False)
            file.truncate()
    elif tipo == "Disband":
        embed = discord.Embed(
            title="**Disband**",
            description=
            f"La banda {banda} ha recibido un Disband por: {motivo}",
            color=discord.Colour.red(),
        )

    embed.set_footer(text="Grupo Oasis | Ilícito")
    await sanciones_channel.send(embed=embed)
    await interaction.response.send_message(
        f"La sanción ha sido publicada en el canal 'sanciones'.",
        ephemeral=True,
        delete_after=5,
    )


# Comando para mostrar el contador de sanciones
@bot.tree.command(
    name="contadorsancion",
    description="Muestra el contador de sanciones para una banda específica.",
)
@app_commands.autocomplete(rol=autocompletar_bandas)
@es_admin()
async def contador_sancion(interaction: discord.Interaction, rol: str):
    with open("sanciones.json", "r", encoding="utf-8") as file:
        sanciones = json.load(file)

    if rol in sanciones and "Aviso" in sanciones[rol]:
        msg = f"Sanciones para {rol}: \nAvisos: {sanciones[rol]['Aviso']}\n"
    else:
        msg = "Esta banda no tiene sanciones registradas."

    await interaction.response.send_message(msg, ephemeral=True)


# Comando para borrar mensajes
@bot.tree.command(
    name="borrarmensajes",
    description="Borra todos los mensajes en el canal actual.",
)
@es_admin()
async def borrar_mensajes(interaction: discord.Interaction):
    channel = interaction.channel
    await channel.purge()
    await interaction.response.send_message(
        "Todos los mensajes en este canal han sido borrados.",
        ephemeral=True,
        delete_after=5)


bot.run(TOKEN)
