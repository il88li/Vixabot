import telebot
import requests
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# توكن البوت
TOKEN = "8137587721:AAGq7kyLc3E0EL7HZ2SKRmJPGj3OLQFVSKo"
bot = telebot.TeleBot(TOKEN)

# قاموس لتخزين حالة المستخدمين
user_states = {}

# إنشاء الكيبورد الرئيسي
def main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    services_btn = InlineKeyboardButton("خدماتنا 🛠️", callback_data="services")
    keyboard.add(services_btn)
    return keyboard

# إنشاء كيبورد الخدمات
def services_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    freepik_btn = InlineKeyboardButton("Freebik 🔍", callback_data="freepik")
    back_btn = InlineKeyboardButton("رجوع ↩️", callback_data="back_main")
    keyboard.add(freepik_btn)
    keyboard.add(back_btn)
    return keyboard

# كيبورد Freebik
def freepik_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    search_btn = InlineKeyboardButton("بحث عن صور 🔎", callback_data="search_images")
    back_btn = InlineKeyboardButton("رجوع ↩️", callback_data="back_services")
    keyboard.add(search_btn)
    keyboard.add(back_btn)
    return keyboard

# كيبورد أثناء البحث
def searching_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    cancel_btn = InlineKeyboardButton("إلغاء البحث ❌", callback_data="cancel_search")
    keyboard.add(cancel_btn)
    return keyboard

# وظيفة البحث في Freebik
def search_freepik_images(query):
    try:
        # ترميز البحث للرابط
        encoded_query = requests.utils.quote(query)
        url = f"https://www.freepik.com/search?format=search&query={encoded_query}"
        
        # إضافة headers لتقليد متصفح
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        images = []
        
        # محاولة العثور على الصور بعدة طرق (لأن هيكل الموقع قد يتغير)
        selectors = [
            'img[data-src]',
            'img.showcase__item__img',
            'img.download__resource__img',
            'img.preview',
            'img.resource__img'
        ]
        
        for selector in selectors:
            img_elements = soup.select(selector)[:10]  # الحد إلى 10 نتائج كحد أقصى
            if img_elements:
                for img in img_elements:
                    img_url = img.get('data-src') or img.get('src')
                    if img_url:
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        if 'freepik' in img_url and img_url not in images:
                            images.append(img_url)
                if images:
                    break
        
        return images[:5]  # إرجاع أول 5 صور فقط
        
    except Exception as e:
        print(f"Error in search: {e}")
        return []

# بداية البوت
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_states[user_id] = 'main'
    
    welcome_text = """مرحباً! 👋

أنا بوت للبحث عن الصور من Freebik. يمكنك استخدام الأزرار ниже للتنقل والبحث."""
    
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard())

# معالجة الردود من الكيبورد
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    message_id = call.message.message_id
    
    try:
        if call.data == "services":
            user_states[user_id] = 'services'
            services_text = "🔧 **خدماتنا المتاحة:**\n\nاختر Freebik للبحث عن الصور المجانية."
            bot.edit_message_text(services_text, user_id, message_id, reply_markup=services_keyboard())
        
        elif call.data == "freepik":
            user_states[user_id] = 'freepik'
            freepik_text = "🔍 **خدمة Freebik للبحث عن الصور:**\n\nيمكنك البحث عن الصور المجانية من Freebik باستخدام زر 'بحث عن صور'."
            bot.edit_message_text(freepik_text, user_id, message_id, reply_markup=freepik_keyboard())
        
        elif call.data == "back_main":
            user_states[user_id] = 'main'
            welcome_text = "مرحباً! 👋\n\nاختر من الخيارات ниже:"
            bot.edit_message_text(welcome_text, user_id, message_id, reply_markup=main_keyboard())
        
        elif call.data == "back_services":
            user_states[user_id] = 'services'
            services_text = "🔧 **خدماتنا المتاحة:**"
            bot.edit_message_text(services_text, user_id, message_id, reply_markup=services_keyboard())
        
        elif call.data == "search_images":
            user_states[user_id] = 'waiting_search'
            search_text = "🔎 **بحث عن الصور**\n\nأرسل كلمة البحث الآن:\n(يمكنك إلغاء البحث بالزر below)"
            bot.edit_message_text(search_text, user_id, message_id, reply_markup=searching_keyboard())
        
        elif call.data == "cancel_search":
            user_states[user_id] = 'freepik'
            freepik_text = "🔍 **خدمة Freebik للبحث عن الصور:**\n\nتم إلغاء البحث. يمكنك البحث مرة أخرى باستخدام زر 'بحث عن صور'."
            bot.edit_message_text(freepik_text, user_id, message_id, reply_markup=freepik_keyboard())
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Error in callback: {e}")
        bot.answer_callback_query(call.id, "حدث خطأ، حاول مرة أخرى")

# معالجة الرسائل النصية للبحث
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.chat.id
    user_state = user_states.get(user_id, 'main')
    
    if user_state == 'waiting_search':
        search_query = message.text.strip()
        
        if not search_query:
            bot.send_message(user_id, "⚠️ الرجاء إدخال كلمة بحث صحيحة.")
            return
        
        # إرسال رسالة الانتظار
        wait_msg = bot.send_message(user_id, f"🔍 جاري البحث عن: `{search_query}`...", parse_mode='Markdown')
        
        try:
            # البحث عن الصور
            images = search_freepik_images(search_query)
            
            if not images:
                bot.edit_message_text(
                    f"❌ لم أجد نتائج للبحث عن: `{search_query}`\n\nحاول بكلمات أخرى.", 
                    user_id, 
                    wait_msg.message_id,
                    parse_mode='Markdown'
                )
                bot.send_message(user_id, "🔍 اختر خياراً:", reply_markup=freepik_keyboard())
                user_states[user_id] = 'freepik'
                return
            
            # إرسال الصور
            bot.edit_message_text(
                f"✅ وجدت {len(images)} صورة للبحث عن: `{search_query}`", 
                user_id, 
                wait_msg.message_id,
                parse_mode='Markdown'
            )
            
            for i, img_url in enumerate(images, 1):
                try:
                    bot.send_photo(user_id, img_url, caption=f"الصورة #{i} | البحث: {search_query}")
                except Exception as e:
                    print(f"Error sending photo {i}: {e}")
                    continue
            
            # إعادة عرض القائمة بعد الانتهاء
            bot.send_message(user_id, "🔍 اختر خياراً:", reply_markup=freepik_keyboard())
            user_states[user_id] = 'freepik'
            
        except Exception as e:
            print(f"Search error: {e}")
            bot.edit_message_text(
                "❌ حدث خطأ أثناء البحث. حاول مرة أخرى لاحقاً.", 
                user_id, 
                wait_msg.message_id
            )
            bot.send_message(user_id, "🔍 اختر خياراً:", reply_markup=freepik_keyboard())
            user_states[user_id] = 'freepik'
    
    else:
        # إذا لم يكن المستخدم في وضع البحث
        if user_state == 'main':
            bot.send_message(user_id, "استخدم الأزرار للتنقل:", reply_markup=main_keyboard())
        elif user_state == 'services':
            bot.send_message(user_id, "خدماتنا المتاحة:", reply_markup=services_keyboard())
        elif user_state == 'freepik':
            bot.send_message(user_id, "خدمة Freebik:", reply_markup=freepik_keyboard())

# معالجة الأخطاء
@bot.message_handler(func=lambda message: True, content_types=['audio', 'video', 'document', 'sticker', 'photo'])
def handle_non_text(message):
    user_id = message.chat.id
    bot.send_message(user_id, "⚠️ أرسل نصاً فقط للبحث عن الصور.")

# تشغيل البوت
if __name__ == "__main__":
    print("🤖 Bot is running...")
    print("Press Ctrl+C to stop the bot")
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except Exception as e:
        print(f"Bot stopped: {e}")
