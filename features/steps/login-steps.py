from behave import when, then
from selenium.webdriver.common.by import By


@when("I visit the Ocotillo staging site when not logged in")
def step_visit_staging(context):
    context.browser.get("https://ocotillo-staging.newmexicowaterdata.org")


@then("I should see the login page with body:")
def step_check_login_page(context):
    expected_text = context.text.strip()  # get the expected block from feature file
    body_text = context.browser.find_element(By.TAG_NAME, "body").text
    assert (
        expected_text in body_text
    ), f"Expected login page text not found.\nExpected:\n{expected_text}\nGot:\n{body_text}"


# ============= EOF =============================================
