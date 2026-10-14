from PIL import Image, ImageDraw, ImageFont
import os
import re

def transliterate(text):
    """Транслитерация русских букв в латинские"""
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    result = ''
    for char in text:
        result += mapping.get(char, char)
    return result

books = [
    ("Преступление и наказание", "Ф. Достоевский", "#2C3E50", "crime_and_punishment"),
    ("Идиот", "Ф. Достоевский", "#1A5276", "idiot"),
    ("Братья Карамазовы", "Ф. Достоевский", "#1B4F72", "brothers_karamazov"),
    ("Белые ночи", "Ф. Достоевский", "#6AB1E1", "nights"),
    ("Война и мир 1", "Л. Толстой", "#7B241C", "war_and_peace1"),
    ("Война и мир 2", "Л. Толстой", "#7B241C", "war_and_peace2"),
    ("Война и мир 3", "Л. Толстой", "#7B241C", "war_and_peace3"),
    ("Война и мир 4", "Л. Толстой", "#7B241C", "war_and_peace4"),
    ("Анна Каренина", "Л. Толстой", "#922B21", "anna_karenina"),
    ("Воскресение", "Л. Толстой", "#A93226", "resurrection"),
    ("Вишнёвый сад", "А. Чехов", "#1E8449", "cherry_orchard"),
    ("Дама с собачкой", "А. Чехов", "#229954", "lady_with_dog"),
    ("Рассказы", "А. Чехов", "#198646", "stories"),
    ("Палата номер шесть", "А. Чехов", "#27AE60", "ward_no_six"),
    ("Русско-китайский разговорник", "И. Иванов", "#00620B", "ra"),
    ("Высшая математика", "А. Алексеев", "#005830", "mat"),
    ("Высшая математика", "А. Алексеев", "#005830", "mat"),
    ("Отцы и дети", "И. Тургенев", "#C64200", "mat1"),
]

os.makedirs("media/covers", exist_ok=True)

for title, author, color, filename in books:
    img = Image.new('RGB', (300, 450), color=color)
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_author = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = ImageFont.load_default()
        font_author = ImageFont.load_default()

    words = title.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font_title)
        if bbox[2] <= 260:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    
    y_title = 150
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        text_width = bbox[2]
        x = (300 - text_width) / 2
        draw.text((x, y_title), line, fill="white", font=font_title)
        y_title += 35
    
    bbox = draw.textbbox((0, 0), author, font=font_author)
    author_width = bbox[2]
    draw.text(((300 - author_width) / 2, 280), author, fill="white", font=font_author)
    
    filepath = f"media/covers/{filename}.png"
    img.save(filepath)
    print(f"Created: {filepath}")