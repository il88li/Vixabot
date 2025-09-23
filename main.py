import telebot
import requests
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# توكن البوت
TOKEN = "8137587721:AAGq7kyLc3E0EL7HZ2SKRmJPGj3OLQFVSKo"
bot = telebot.TeleBot(TOKEN)

# قاموس لتخزين حالة المستخدمين ونتائج البحث
user_data = {}

# إنشاء الكيبورد الرئيسي
def main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    services_btn = InlineKeyboardButton("خدماتنا", callback_data="services")
    keyboard.add(services_btn)
    return keyboard

# إنشاء كيبورد الخدمات
def services_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    freepik_btn = InlineKeyboardButton("Freebik", callback_data="freepik")
    back_btn = InlineKeyboardButton("رجوع", callback_data="back_main")
    keyboard.add(freepik_btn, back_btn)
    return keyboard

# كيبورد Freebik
def freepik_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    search_btn = InlineKeyboardButton("بحث عن صور", callback_data="search_images")
    back_btn = InlineKeyboardButton("رجوع", callback_data="back_services")
    keyboard.add(search_btn, back_btn)
    return keyboard

# كيبورد التنقل بين الصور
def navigation_keyboard(current_index, total_images):
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    
    if current_index > 0:
        prev_btn = InlineKeyboardButton("السابق", callback_data=f"prev_{current_index}")
        buttons.append(prev_btn)
    
    counter_btn = InlineKeyboardButton(f"{current_index + 1}/{total_images}", callback_data="counter")
    buttons.append(counter_btn)
    
    if current_index < total_images - 1:
        next_btn = InlineKeyboardButton("التالي", callback_data=f"next_{current_index}")
        buttons.append(next_btn)
    
    if buttons:
        keyboard.add(*buttons)
    
    new_search_btn = InlineKeyboardButton("بحث جديد", callback_data="new_search")
    back_btn = InlineKeyboardButton("رجوع", callback_data="back_freepik")
    keyboard.add(new_search_btn, back_btn)
    
    return keyboard

# وظيفة البحث في Freebik
def search_freepik_images(query):
    try:
        encoded_query = requests.utils.quote(query)
        url = f"https://www.freepik.com/search?format=search&query={encoded_query}"
        
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
        
        selectors = [
            'img[data-src]',
            'img.showcase__item__img',
            'img.download__resource__img',
            'img.preview',
            'img.resource__img'
        ]
        
        for selector in selectors:
            img_elements = soup.select(selector)[:10]
            if img_elements:
                for img in img_elements:
                    img_url = img.get('data-src') or img.get('src')
                    if img_url:
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        if 'freepik' in img_url and img_url not in images:
                            # محاولة الحصول على صورة بدقة أفضل
                            if '_640.jpg' in img_url:
                                img_url = img_url.replace('_640.jpg', '_1024.jpg')
                            elif '_360.jpg' in img_url:
                                img_url = img_url.replace('_360.jpg', '_1024.jpg')
                            images.append(img_url)
                if images:
                    break
        
        return images[:8]
        
    except Exception as e:
        print(f"Error in search: {e}")
        return []

# بداية البوت
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_data[user_id] = {'state': 'main'}
    
    welcome_text = "مرحباً\n\nاختر من الخيارات أدناه:"
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard())

# معالجة الردود من الكيبورد
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    message_id = call.message.message_id
    
    try:
        if user_id not in user_data:
            user_data[user_id] = {'state': 'main'}
        
        # التنقل الرئيسي
        if call.data == "services":
            user_data[user_id]['state'] = 'services'
            services_text = "خدماتنا المتاحة:"
            bot.edit_message_text(services_text, user_id, message_id, reply_markup=services_keyboard())
        
        elif call.data == "freepik":
            user_data[user_id]['state'] = 'freepik'
            freepik_text = "خدمة Freebik للبحث عن الصور:"
            bot.edit_message_text(freepik_text, user_id, message_id, reply_markup=freepik_keyboard())
        
        elif call.data == "back_main":
            user_data[user_id]['state'] = 'main'
            welcome_text = "مرحباً\n\nاختر من الخيارات أدناه:"
            bot.edit_message_text(welcome_text, user_id, message_id, reply_markup=main_keyboard())
        
        elif call.data == "back_services":
            user_data[user_id]['state'] = 'services'
            services_text = "خدماتنا المتاحة:"
            bot.edit_message_text(services_text, user_id, message_id, reply_markup=services_keyboard())
        
        elif call.data == "back_freepik":
            user_data[user_id]['state'] = 'freepik'
            freepik_text = "خدمة Freebik للبحث عن الصور:"
            bot.edit_message_text(freepik_text, user_id, message_id, reply_markup=freepik_keyboard())
        
        elif call.data == "search_images":
            user_data[user_id]['state'] = 'waiting_search'
            search_text = "أرسل كلمة البحث للبحث عن الصور في Freebik:"
            bot.edit_message_text(search_text, user_id, message_id)
        
        elif call.data == "new_search":
            user_data[user_id]['state'] = 'waiting_search'
            search_text = "أرسل كلمة البحث الجديدة:"
            bot.edit_message_text(search_text, user_id, message_id)
        
        # التنقل بين الصور
        elif call.data.startswith(('prev_', 'next_')):
            if 'search_results' not in user_data[user_id]:
                bot.answer_callback_query(call.id, "لا توجد نتائج للبحث")
                return
            
            current_index = int(call.data.split('_')[1])
            search_results = user_data[user_id]['search_results']
            search_query = user_data[user_id]['search_query']
            
            if call.data.startswith('prev_'):
                new_index = current_index - 1
            else:
                new_index = current_index + 1
            
            if 0 <= new_index < len(search_results):
                try:
                    # تحرير الوسائط مع الصورة الجديدة
                    media = telebot.types.InputMediaPhoto(
                        search_results[new_index],
                        caption=f"البحث: {search_query}\nالصورة {new_index + 1} من {len(search_results)}"
                    )
                    
                    bot.edit_message_media(
                        media=media,
                        chat_id=user_id,
                        message_id=message_id,
                        reply_markup=navigation_keyboard(new_index, len(search_results))
                    )
                    
                    bot.answer_callback_query(call.id)
                except Exception as e:
                    print(f"Error editing media: {e}")
                    bot.answer_callback_query(call.id, "خطأ في تحميل الصورة")
            else:
                bot.answer_callback_query(call.id, "لا توجد المزيد من الصور")
        
        elif call.data == "counter":
            bot.answer_callback_query(call.id)
        
        else:
            bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Error in callback: {e}")
        try:
            bot.answer_callback_query(call.id, "حدث خطأ، حاول مرة أخرى")
        except:
            pass

# معالجة الرسائل النصية للبحث
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.chat.id
    
    if user_id not in user_data:
        user_data[user_id] = {'state': 'main'}
    
    user_state = user_data[user_id].get('state', 'main')
    
    if user_state == 'waiting_search':
        search_query = message.text.strip()
        
        if not search_query:
            bot.send_message(user_id, "الرجاء إدخال كلمة بحث صحيحة.")
            return
        
        # إرسال رسالة الانتظار
        wait_msg = bot.send_message(user_id, f"جاري البحث عن: {search_query}...")
        
        try:
            # البحث عن الصور
            images = search_freepik_images(search_query)
            
            if not images:
                bot.edit_message_text(
                    f"لم أجد نتائج للبحث عن: {search_query}\nحاول بكلمات أخرى.", 
                    user_id, 
                    wait_msg.message_id
                )
                bot.send_message(user_id, "اختر خياراً:", reply_markup=freepik_keyboard())
                user_data[user_id]['state'] = 'freepik'
                return
            
            # حفظ نتائج البحث
            user_data[user_id]['search_results'] = images
            user_data[user_id]['search_query'] = search_query
            user_data[user_id]['state'] = 'viewing_results'
            
            # إرسال أول صورة مع أزرار التنقل
            caption = f"البحث: {search_query}\nالصورة 1 من {len(images)}"
            keyboard = navigation_keyboard(0, len(images))
            
            # حذف رسالة الانتظار
            bot.delete_message(user_id, wait_msg.message_id)
            
            # إرسال الصورة الأولى
            bot.send_photo(
                user_id, 
                images[0], 
                caption=caption,
                reply_markup=keyboard
            )
            
        except Exception as e:
            print(f"Search error: {e}")
            try:
                bot.edit_message_text(
                    "حدث خطأ أثناء البحث. حاول مرة أخرى لاحقاً.", 
                    user_id, 
                    wait_msg.message_id
                )
            except:
                pass
            bot.send_message(user_id, "اختر خياراً:", reply_markup=freepik_keyboard())
            user_data[user_id]['state'] = 'freepik'
    
    else:
        if user_state == 'main':
            bot.send_message(user_id, "استخدم الأزرار للتنقل:", reply_markup=main_keyboard())
        elif user_state == 'services':
            bot.send_message(user_id, "خدماتنا المتاحة:", reply_markup=services_keyboard())
        elif user_state == 'freepik':
            bot.send_message(user_id, "خدمة Freebik:", reply_markup=freepik_keyboard())

# معالجة أنواع المحتوى الأخرى
@bot.message_handler(content_types=['audio', 'video', 'document', 'sticker', 'photo'])
def handle_non_text(message):
    user_id = message.chat.id
    bot.send_message(user_id, "يرجى إرسال نص فقط للبحث عن الصور.")

# تشغيل البوت
if __name__ == "__main__":
    print("Bot is running...")
    print("Press Ctrl+C to stop the bot")
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except Exception as e:
        print(f"Bot stopped: {e}")
