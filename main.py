import os
import base64
import mimetypes
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from google import genai
from google.genai import types

# ⚠️ استبدل هذا بـ token البوت الحقيقي من BotFather
BOT_TOKEN = "8398354970:AAGcDT0WAIUvT2DnTqyxfY1Q8h2b5rn-LIo"
GEMINI_API_KEY = "AIzaSyCAoTSdg_KIOZTv9ggh3tSXU7Owu514l8o"

# تخزين حالات المستخدمين
user_states = {}
user_data = {}

# أمر البدء /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("خدمات البوت", callback_data="services")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🚀 مرحباً! أنا بوت الذكاء الاصطناعي لإنشاء وتعديل الصور باستخدام Nano Banana (Gemini).\n\n"
        "انقر على الزر أدناه لبدء استخدام الخدمات.",
        reply_markup=reply_markup
    )

# معالجة الضغط على الأزرار
async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "services":
        # عرض قائمة الخدمات
        keyboard = [
            [InlineKeyboardButton("🖼 إنشاء صورة", callback_data="create_image")],
            [InlineKeyboardButton("✏️ تعديل صورة", callback_data="edit_image")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 اختر الخدمة التي تريدها:",
            reply_markup=reply_markup
        )
    
    elif data == "create_image":
        user_states[user_id] = "waiting_for_prompt"
        await query.edit_message_text(
            "🎨 أرسل لي وصف الصورة التي تريد إنشاءها:\n\n"
            "📝 مثال: A beautiful sunset over mountains with a lake in the foreground\n"
            "💡 أفضل النتائج تكون باللغة الإنجليزية"
        )
    
    elif data == "edit_image":
        user_states[user_id] = "waiting_for_image"
        await query.edit_message_text(
            "🖼 أرسل الصورة التي تريد تعديلها أولاً."
        )
    
    elif data == "back_to_main":
        # تنظيف البيانات والعودة للقائمة الرئيسية
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_data:
            del user_data[user_id]
            
        keyboard = [
            [InlineKeyboardButton("خدمات البوت", callback_data="services")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏠 مرحباً مرة أخرى! اختر خدمة للبدء.",
            reply_markup=reply_markup
        )

# دالة لإنشاء الصور باستخدام Gemini
def create_image(prompt):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # استخدام نموذج إنشاء الصور
        model = "gemini-2.0-flash-exp-image-generation"
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]
        
        config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
        
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        
        results = {"images": [], "texts": []}
        
        if (response.candidates and response.candidates[0].content and 
            response.candidates[0].content.parts):
            
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    # حفظ الصورة في ملف مؤقت
                    image_data = part.inline_data.data
                    mime_type = part.inline_data.mime_type
                    file_extension = mimetypes.guess_extension(mime_type) or '.png'
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                        temp_file.write(image_data)
                        results["images"].append(temp_file.name)
                
                elif hasattr(part, 'text') and part.text:
                    results["texts"].append(part.text)
        
        return results
        
    except Exception as e:
        return {"error": f"❌ خطأ في إنشاء الصورة: {str(e)}"}

# دالة لتعديل الصور باستخدام Gemini
def edit_image(image_path, edit_prompt):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # قراءة الصورة وتحويلها لـ base64
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # استخدام نموذج يدعم الصور كمدخل
        model = "gemini-1.5-flash"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text="هذه الصورة الأصلية. قم بتعديلها حسب الطلب:"),
                    types.Part.from_inline_data(
                        mime_type="image/jpeg",
                        data=base64.b64decode(image_data)
                    ),
                    types.Part.from_text(text=f"التعديل المطلوب: {edit_prompt}"),
                ],
            ),
        ]
        
        config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
        
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        
        results = {"images": [], "texts": []}
        
        if (response.candidates and response.candidates[0].content and 
            response.candidates[0].content.parts):
            
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    # حفظ الصورة المعدلة
                    image_data = part.inline_data.data
                    mime_type = part.inline_data.mime_type
                    file_extension = mimetypes.guess_extension(mime_type) or '.png'
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                        temp_file.write(image_data)
                        results["images"].append(temp_file.name)
                
                elif hasattr(part, 'text') and part.text:
                    results["texts"].append(part.text)
        
        return results
        
    except Exception as e:
        return {"error": f"❌ خطأ في تعديل الصورة: {str(e)}"}

# معالجة الرسائل النصية من المستخدم
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text
    
    if user_id not in user_states:
        await update.message.reply_text("⚠️ يرجى استخدام الأزرار للتفاعل مع البوت.")
        return
    
    state = user_states[user_id]
    
    if state == "waiting_for_prompt":
        await update.message.reply_text("⏳ جاري إنشاء الصورة باستخدام Nano Banana...")
        
        try:
            result = create_image(user_message)
            
            if "error" in result:
                await update.message.reply_text(result["error"])
            else:
                # إرسال النتائج (صور ونصوص)
                sent_results = False
                
                # إرسال الصور (النتيجة الأولى والثانية)
                if result["images"]:
                    for i, image_path in enumerate(result["images"][:2]):
                        with open(image_path, 'rb') as photo:
                            await update.message.reply_photo(
                                photo=photo,
                                caption=f"🖼 الصورة المنشأة {i+1}"
                            )
                        os.unlink(image_path)  # حذف الملف المؤقت
                        sent_results = True
                
                # إرسال النصوص (النتيجة الأولى والثانية)
                if result["texts"]:
                    for i, text in enumerate(result["texts"][:2]):
                        await update.message.reply_text(f"📝 النتيجة النصية {i+1}:\n{text}")
                        sent_results = True
                
                if not sent_results:
                    await update.message.reply_text("❌ لم أتمكن من إنشاء أي نتائج. حاول مرة أخرى.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ عذراً، حدث خطأ: {str(e)}")
        
        # العودة للقائمة الرئيسية
        del user_states[user_id]
        await show_main_menu(update.message)
    
    elif state == "waiting_for_edit_prompt":
        user_data[user_id]["edit_prompt"] = user_message
        await update.message.reply_text("⏳ جاري تعديل الصورة...")
        
        try:
            result = edit_image(user_data[user_id]["image_path"], user_message)
            
            if "error" in result:
                await update.message.reply_text(result["error"])
            else:
                # إرسال النتائج (صور ونصوص)
                sent_results = False
                
                if result["images"]:
                    for i, image_path in enumerate(result["images"][:2]):
                        with open(image_path, 'rb') as photo:
                            await update.message.reply_photo(
                                photo=photo,
                                caption=f"✏️ الصورة المعدلة {i+1}"
                            )
                        os.unlink(image_path)
                        sent_results = True
                
                if result["texts"]:
                    for i, text in enumerate(result["texts"][:2]):
                        await update.message.reply_text(f"📝 الوصف {i+1}:\n{text}")
                        sent_results = True
                
                if not sent_results:
                    await update.message.reply_text("❌ لم أتمكن من إنشاء أي نتائج. حاول مرة أخرى.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ عذراً، حدث خطأ: {str(e)}")
        
        # تنظيف البيانات
        if user_id in user_data and "image_path" in user_data[user_id]:
            os.unlink(user_data[user_id]["image_path"])
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_data:
            del user_data[user_id]
        
        await show_main_menu(update.message)

# معالجة الصور المرسلة
async def handle_image_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id in user_states and user_states[user_id] == "waiting_for_image":
        # حفظ الصورة مؤقتاً
        photo_file = await update.message.photo[-1].get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            await photo_file.download_to_drive(temp_file.name)
            
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]["image_path"] = temp_file.name
        
        # الانتقال لانتظار وصف التعديل
        user_states[user_id] = "waiting_for_edit_prompt"
        
        await update.message.reply_text(
            "✅ تم استلام الصورة بنجاح!\n\n"
            "📝 الآن أرسل وصف التعديلات التي تريدها:\n"
            "مثال: Change the background to a beach sunset and add a smile"
        )
    else:
        await update.message.reply_text("⚠️ يرجى اختيار 'تعديل صورة' أولاً من القائمة.")

# عرض القائمة الرئيسية
async def show_main_menu(message):
    keyboard = [
        [InlineKeyboardButton("خدمات البوت", callback_data="services")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("🎯 اختر خدمة أخرى إذا أردت:", reply_markup=reply_markup)

# معالجة الأوامر غير المعروفة
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ يرجى استخدام الأمر /start للبدء.")

# الدالة الرئيسية لتشغيل البوت
def main():
    # التأكد من وجود token البوت
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: يرجى تعيين BOT_TOKEN الحقيقي")
        return
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالجات الأحداث
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image_message))
    application.add_handler(MessageHandler(filters.ALL, handle_unknown))
    
    # تشغيل البوت
    print("🤖 البوت يعمل الآن...")
    print("📍 استخدم /start في تلجرام للبدء")
    application.run_polling()

if __name__ == "__main__":
    main()
