import discord
from discord.ext import commands
import asyncio
from discord import app_commands
from discord.app_commands import Choice
import json

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

with open("parametros.json", "r", encoding="utf-8") as f:
    config = json.load(f)
with open("secrets.json", "r", encoding="utf-8") as e:
    secrets = json.load(e)

tipo_sanciones = config["tipoSanciones"]
tipo_bandas = config["Bandas"]
TOKEN = secrets["TOKEN"]
ID_Discord = secrets["ID_Servidor"]


def actualizar_bandas(nombre_banda):
    with open("parametros.json", "r+", encoding="utf-8") as file:
        data = json.load(file)
        data["Bandas"].append({"name": nombre_banda, "value": nombre_banda})
        file.seek(0)
        json.dump(data, file, indent=4, ensure_ascii=False)
        file.truncate()


def es_admin():

    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator

    return discord.app_commands.check(predicate)


@bot.event
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    if isinstance(error, discord.app_commands.errors.CheckFailure):
        if interaction.response.is_done():
            # Si ya se envió una respuesta inicial, se utiliza followup para enviar mensajes adicionales
            await interaction.followup.send(
                "No tienes permiso para ejecutar este comando.", ephemeral=True
            )
        else:
            # Si no se ha enviado una respuesta inicial, se utiliza send_message para responder
            await interaction.response.send_message(
                "No tienes permiso para ejecutar este comando.", ephemeral=True
            )
    else:
        print(f"Un error ocurrió al ejecutar un comando: {error}")


@bot.event
async def on_ready():
    print(f"Logged in as miau")
    try:
        # Sincronización en un canal específico
        guild_id = (
            ID_Discord  # El ID del canal, tienes que tener DC en modo desarrollador
        )
        guild = discord.Object(id=guild_id)
        await bot.tree.sync(guild=guild)
        print(f"Synced commands to guild ID {guild_id}")
        # Sincronizacion de forma global
        # await bot.tree.sync()
    except Exception as e:
        print(e)
    await bot.tree.sync()


@bot.tree.command(
    name="crearbanda",
    description="Crea una banda con el nombre y el color especificados.",
)
@es_admin()  # Comprueba si tiene rol de admin
async def crear_banda(interaction: discord.Interaction, nombre: str, color_hex: str):
    # Convertir el código hexadecimal a un objeto Colour
    try:
        color = discord.Colour(int(color_hex.lstrip("#"), 16))
    except ValueError:
        await interaction.response.send_message(
            "El código de color proporcionado no es válido.",
            ephemeral=True,
            delete_after=5,
        )
        return

    # Crear la categoría
    categoria = await interaction.guild.create_category(name=nombre)

    # Crear el rol con el color proporcionado
    rol = await interaction.guild.create_role(name=nombre, color=color)

    # Establecer permisos de canal
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(
            read_messages=False
        ),
        rol: discord.PermissionOverwrite(read_messages=True),
    }

    # Crear los canales con los permisos establecidos
    await categoria.create_text_channel(name="lideres-staff", overwrites=overwrites)
    await categoria.create_text_channel(name="entradas-salidas", overwrites=overwrites)
    await categoria.create_text_channel(name="ventas", overwrites=overwrites)
    actualizar_bandas(nombre)
    await interaction.response.send_message(
        f'Se ha creado la banda "{nombre}" con éxito y se han establecido los permisos.',
        ephemeral=True,
        delete_after=5,
    )


@bot.tree.command(
    name="eliminarbanda",
    description="Elimina una banda, el rol y expulsa a quienes tengan ese rol",
)
@app_commands.choices(
    banda=[
        app_commands.Choice(name=banda["name"], value=banda["value"])
        for banda in config["Bandas"]
    ]
)
@es_admin()  # Comprueba si tiene rol de admin
async def eliminar_banda(
    interaction: discord.Interaction, banda: app_commands.Choice[str]
):
    nombre = banda.value
    guild = interaction.guild
    # Buscar la categoría por nombre
    categoria = discord.utils.get(interaction.guild.categories, name=nombre)

    # También buscar el rol por nombre
    rol = discord.utils.get(interaction.guild.roles, name=nombre)

    if categoria is None and rol is None:
        await interaction.response.send_message(
            f"No se encontró la banda o el rol con el nombre '{nombre}'.",
            ephemeral=True,
            delete_after=5,
        )
        return

    # Expulsar miembros con el rol
    if rol is not None:
        for member in list(guild.members):
            # Verificar si el miembro solo tiene el rol específico
            if (
                len(member.roles) == 2 and rol in member.roles
            ):  # Discord siempre incluye un "rol @everyone" invisible, por eso se comprueba con 2
                try:
                    await member.kick(reason=f"Eliminación de la banda {nombre}")
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

        # Después de eliminar la banda en Discord...
    config["Bandas"] = [banda for banda in config["Bandas"] if banda["value"] != nombre]

    # Guardar los cambios en parametros.json
    with open("parametros.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

    await interaction.response.send_message(
        f"Se ha eliminado la banda y rol '{nombre}' con éxito.",
        ephemeral=True,
        delete_after=5,
    )


@bot.tree.command(
    name="anuncio",
    description="Lanza un comunicado en el canal de comunicados mencionando a todos, utilizar \n para saltos de linea",
)
@es_admin()
async def anuncio(interaction: discord.Interaction, *, titulo: str, contenido: str):
    comunicados_channel = discord.utils.get(
        interaction.guild.text_channels, name="comunicados"
    )

    if not comunicados_channel:
        await interaction.response.send_message(
            "El canal 'comunicados' no se encuentra en el servidor.",
            ephemeral=True,
            delete_after=5,
        )
        return

    # Formatea el contenido para crear saltos de línea donde sea necesario
    contenido_formateado = contenido.replace("\\n", "\n")

    embed = discord.Embed(
        title=titulo, description=contenido_formateado, color=discord.Colour.blue()
    )
    embed.set_footer(text="Grupo Oasis | Ilícito")

    try:
        # Enviar el mensaje @everyone en el canal comunicados
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


async def autocompletar_bandas(interaction: discord.Interaction, current: str):
    # Este decorador permite a la función ser una función de autocompletado para discord.py
    roles = (
        await interaction.guild.fetch_roles()
    )  # Obtiene todos los roles del servidor
    return [
        app_commands.Choice(
            name=role.name, value=role.name
        )  # Usa el nombre del rol para ambas propiedades por simplicidad
        for role in roles
        if current.lower() in role.name.lower()
    ][
        :25
    ]  # Discord solo permite 25 opciones de autocompletado


@bot.tree.command(
    name="darbanda", description="Asigna un usuario a un rol existente en el servidor."
)
@es_admin()  # Asegúrate de que solo los administradores puedan ejecutar este comando.
@app_commands.autocomplete(banda=autocompletar_bandas)
async def dar_banda(
    interaction: discord.Interaction, usuario: discord.User, banda: str
):
    # La función de autocompletado manejará la sugerencia de los nombres de los roles
    rol = discord.utils.get(interaction.guild.roles, name=banda)
    if rol is None:
        await interaction.response.send_message(
            f"No se encontró el rol '{banda}'.", ephemeral=True
        )
        return

    member = interaction.guild.get_member(usuario.id)
    if member is None:
        await interaction.response.send_message(
            "No se encontró al usuario en el servidor.", ephemeral=True
        )
        return

    await member.add_roles(rol)
    await interaction.response.send_message(
        f"El rol '{rol.name}' ha sido asignado al usuario {usuario.display_name}.",
        ephemeral=True,
    )


@bot.tree.command(
    name="sancion", description="Comando para comunicar una sancion a un usuario."
)
@es_admin()  # Asegúrate de que solo los administradores puedan ejecutar este comando.
@app_commands.describe(
    tipo="Elige entre Aviso, Falta o Disband.",
    banda="Nombre de las bandas de la lista",
    motivo="Detalles de la sanción.",
)
@app_commands.choices(
    tipo=[
        app_commands.Choice(name=opcion["name"], value=opcion["value"])
        for opcion in tipo_sanciones
    ],
    banda=[
        app_commands.Choice(name=bandas["name"], value=bandas["value"])
        for bandas in tipo_bandas
    ],
)
async def sancion(
    interaction: discord.Interaction, tipo: str, *, banda: str, motivo: str
):
    # Define los colores posibles en función del tipo de sanción
    colores = {
        "Aviso": discord.Colour.orange(),
        "Falta": discord.Colour.red(),
        "Disband": discord.Colour(0x000000),
    }

    # Selecciona el color basado en el tipo de sanción
    color_embed = colores[tipo]

    # Crea el embed con el texto y el color correspondiente
    embed = discord.Embed(
        title="**Sanción**",
        description=f"La banda {banda} ha recibido un/a **{tipo}** por: {motivo}",
        color=color_embed,
    )
    embed.set_footer(text="Grupo Oasis | Ilícito")

    # Encuentra el canal de "sanciones" en el servidor
    sanciones_channel = discord.utils.get(
        interaction.guild.text_channels, name="sanciones"
    )
    if sanciones_channel is None:
        # Si el canal no existe, informa al usuario y no hagas nada más
        await interaction.response.send_message(
            "El canal 'sanciones' no existe.", ephemeral=True, delete_after=5
        )
        return

    # Envía el embed en el canal de sanciones
    await sanciones_channel.send(embed=embed)
    # Confirma que el mensaje fue enviado
    await interaction.response.send_message(
        f"La sanción ha sido publicada en el canal 'sanciones'.",
        ephemeral=True,
        delete_after=5,
    )


# Inicia tu bot con el token proporcionado
bot.run(TOKEN)
