from fastapi import FastAPI, Request, Depends, status, HTTPException, Body, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from typing import Optional, Union
from pydantic import BaseModel, EmailStr
import requests, secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import getenv
from deta import Base
from html import escape

from dotenv import load_dotenv

load_dotenv()
from config import get_env_variable

filled_forms_db = Base("FormToEmailServiceFilledForms")
alias_db = Base("FormToEmailServiceAliases")

from uuid import uuid4

demo_credentials_part = ""
if (get_env_variable("ADMIN_USERNAME", "demo") == "demo"):
    demo_credentials_part = """
### Demo Credentials    
* **Username:** demo
* **Password:** demo

    """
description_of_fastapi = f"""

## Simple and Hassle Free Service For All Your Form Needs

{demo_credentials_part}

``You can change settings in FormToEmailServiceSettings database.``

* **ADMIN_USERNAME** and **ADMIN_PASSWORD** (which is asked on deployment) is used as password and username. 
* Username and password is required when creating an alias.

- - -

### [📝Test Now With Creating Your Alias](create-test-alias)
- - -



## Deployment 💻 
You can deploy your own instance of FormToEmailService using the button below. You will need a [Deta](https://www.deta.sh/) account.  
[![Click Here To Deploy Your Own FreeEmailValidationApi  💻️](https://button.deta.dev/1/svg)](https://go.deta.dev/deploy?repo=https://github.com/mehmetcanfarsak/FormToEmailService)

## Stages of a Form Post

* Posted form details are recorded in database. 
* User is asked to fill captcha.
* After clicking submit button captcha is check from (form_post_captcha_submit) endpoint.
    * If user wrote wrong text of captcha captcha, error is prompted.
* If  user wrote right text of captcha captcha, success animation is showed and  email is sent to email of the ailas.
 
"""
app = FastAPI(title="📭 Form To Email Service", description=description_of_fastapi,
              contact={"url": "https://github.com/mehmetcanfarsak", "Name": "Mehmet Can Farsak"})

security = HTTPBasic()


class AdminUser(BaseModel):
    username: str
    password: str


def get_admin_user(credentials: HTTPBasicCredentials = Depends(security)):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = get_env_variable("ADMIN_USERNAME", "demo").encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = get_env_variable("ADMIN_PASSWORD", "demo").encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return AdminUser(username=correct_username_bytes.decode(), password=correct_password_bytes.decode())


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates("templates")


class CreateAliasResponseModel(BaseModel):
    is_alias_created: bool


class CaptchaSubmitResponseModel(BaseModel):
    is_submit_successful: bool


class AliasModel(BaseModel):
    alias: str
    email: EmailStr


class FilledFormModel(BaseModel):
    key: str
    captcha_id: str
    alias: str
    text_of_captcha: str
    is_email_sent: bool = False
    form_inputs: dict


def send_email(email_subject: str, email_body: str, receiver_email: EmailStr):
    sender_address = get_env_variable("SENDER_EMAIL_ADDRESS")
    sender_pass = get_env_variable("SENDER_MAIL_PASSWORD")
    receiver_address = receiver_email
    # Setup the MIME
    message = MIMEMultipart()
    message['From'] = sender_address
    message['To'] = receiver_address
    message['Subject'] = email_subject  # The subject line
    # The body and the attachments for the mail
    message.attach(MIMEText(email_body, 'html'))
    # Create SMTP session for sending the mail
    session = smtplib.SMTP(get_env_variable("SENDER_SERVER_ADDRESS"),
                           int(get_env_variable("SENDER_SMTP_PORT")))  # use gmail with port
    session.starttls()  # enable security
    session.login(sender_address, sender_pass)  # login with mail_id and password
    text = message.as_string()
    session.sendmail(sender_address, receiver_address, text)
    session.quit()

    return


@app.get("/", include_in_schema=False, response_class=RedirectResponse)
def root():
    return RedirectResponse("/docs")


@app.get("/test-sending-email",
         description="If you encounter any error, you just check your email settings with this endpoint.",
         tags=["Check if Your Email Settings are Okay"])
def test_sending_email(receiver_email: EmailStr = Query("user@example.com"),
                       credentials: HTTPBasicCredentials = Depends(get_admin_user)):
    import traceback
    try:
        send_email(email_subject="Test from FormToEmailService",
                   email_body="This is a test mail. If you see this email in your inbox, your email settings are properly installed.",
                   receiver_email=receiver_email)
    except:
        return "Got Error. Error Details: " + str(traceback.format_exc())

    return "Email Sent Successfully"


@app.post("/create-alias", tags=['Create Alias'], response_model=CreateAliasResponseModel)
def create_alias(alias: AliasModel, credentials: HTTPBasicCredentials = Depends(get_admin_user)):
    if (alias_db.get(alias.alias)):
        return CreateAliasResponseModel(is_alias_created=False)
    alias = alias.dict()
    alias['key'] = alias['alias']
    alias_db.put(alias)
    return CreateAliasResponseModel(is_alias_created=True)


@app.get("/create-test-alias", include_in_schema=False)
def create_test_alias(request: Request, credentials: HTTPBasicCredentials = Depends(get_admin_user)):
    return templates.TemplateResponse("create_test_alias.html", {"request": request})


@app.post("/create-alias-and-show-test-form", include_in_schema=False)
def create_alias_and_show_test_form(request: Request, alias: str = Form(), email: EmailStr = Form(),
                                    credentials: HTTPBasicCredentials = Depends(get_admin_user)):
    if (alias_db.get(alias)):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail="Alias exists. Please select different alias")
    alias_db.put({"key": alias, "email": email, "alias": alias})
    return templates.TemplateResponse("create_alias_and_show_test_form.html", {"request": request, "alias": alias})


@app.get('/show-captcha-image/{filled_form_key}.png', response_class=StreamingResponse, include_in_schema=False)
def show_captcha_image(filled_form_key: str):
    filled_form = filled_forms_db.get(filled_form_key)
    if (not filled_form):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Captcha Not Found")
    response = requests.get(
        get_env_variable("PRIVATE_SIMPLE_CAPTCHA_API_LINK",
                         "https://PrivateSimpleCaptchaApi.deta.dev") + "/get-captcha-image/" + filled_form[
            'captcha_id'] + ".png", stream=True)
    return StreamingResponse(response.raw, media_type="")


@app.post("/{alias}/captcha-submit", include_in_schema=False,
          response_model=CaptchaSubmitResponseModel)
def form_post_captcha_submit(alias: str, filled_form_key: str = Body(), text_of_captcha: str = Body()):
    filled_form = filled_forms_db.get(filled_form_key)
    if (not filled_form):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if (filled_form['alias'] != alias):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Alias mismatch!")
    if (filled_form['is_email_sent'] == True):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Submitted Before!")
    if (filled_form['text_of_captcha'] != text_of_captcha):
        return CaptchaSubmitResponseModel(is_submit_successful=False)

    requests.post(get_env_variable("DETA_EVENT_QUEUE_LINK",
                                   "https://DetaEventQueue.deta.dev") + "/receive-event?password=" + get_env_variable(
        "DETA_EVENT_QUEUE_PASSWORD", "demo"), json={
        "url_to_send_request": f"https://{getenv('DETA_PATH')}.deta.dev/form-send-email-job?filled_form_key={filled_form_key}&ADMIN_USERNAME={get_env_variable('ADMIN_USERNAME', 'demo')}&ADMIN_PASSWORD={get_env_variable('ADMIN_PASSWORD', 'demo')}",
        "call_url_after": 0,
        "max_try_count": 3,
        "timeout_for_request": 6,
        "event_tags": []
    })

    return CaptchaSubmitResponseModel(is_submit_successful=True)


@app.get('/form-send-email-job', include_in_schema=False)
def form_send_email_job(filled_form_key: str, ADMIN_USERNAME: str, ADMIN_PASSWORD: str):
    if (ADMIN_USERNAME != get_env_variable("ADMIN_USERNAME", "demo")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username or password is wrong!")
    if (ADMIN_PASSWORD != get_env_variable("ADMIN_PASSWORD", "demo")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Username or password is wrong!")
    filled_form = filled_forms_db.get(filled_form_key)
    if (filled_form['is_email_sent'] == True):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Submitted Before!")
    alias_email = alias_db.get(filled_form['alias'])['email']

    filled_form['is_email_sent'] = True
    filled_forms_db.put(filled_form)

    mail_string_of_form_details = ""
    for form_input_key in filled_form['form_inputs']:
        mail_string_of_form_details += "<b>" + escape(str(form_input_key)) + "</b> : " + escape(
            str(filled_form['form_inputs'][
                    form_input_key])) + " <br> "
    mail_content = f"""Hello, <br>
    New Form Submitted. Here is details of the form.<br><br>

    {mail_string_of_form_details}
    <br><br><br>
    Have a good day!
    """
    subject = 'A New Form is submitted to your alias: ' + str(filled_form['alias'])
    send_email(email_subject=subject, email_body=mail_content, receiver_email=alias_email)
    return "OK"


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@app.post("/{alias}", response_class=HTMLResponse, tags=["Submit A Form Response"])
async def form_post_first_stage(alias: str, request: Request, test_name_variable: Union[str, None] = Form("John Doe"),
                                test_sender_message_variable: Union[str, None] = Form("This is test message")):
    form = await request.form()
    if (not alias_db.get(alias)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias Not Found!")
    filled_form_key = str(uuid4())
    captcha_response = requests.get(get_env_variable("PRIVATE_SIMPLE_CAPTCHA_API_LINK",
                                                     "https://PrivateSimpleCaptchaApi.deta.dev") + "/create-random-captcha").json()
    filled_form = FilledFormModel(
        key=filled_form_key,
        captcha_id=captcha_response['captcha_id'],
        alias=alias,
        text_of_captcha=captcha_response['text_of_captcha'],
        form_inputs={}
    )
    for form_key in form:
        filled_form.form_inputs[form_key] = form[form_key]
    filled_forms_db.put(filled_form.dict())

    return templates.TemplateResponse("form_post_first_stage.html",
                                      {"request": request, "filled_form_key": filled_form_key, "alias": alias})
