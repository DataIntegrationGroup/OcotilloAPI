from selenium import webdriver


def before_all(context):
    """Executed once before all tests"""
    # Configure Selenium driver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run without opening a browser window
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")

    # Mobile emulation (optional for field technician workflows)
    # mobile_emulation = { "deviceName": "Pixel 5" }
    # options.add_experimental_option("mobileEmulation", mobile_emulation)

    context.browser = webdriver.Chrome(options=options)
    context.browser.implicitly_wait(5)  # wait for elements to appear


def before_scenario(context, scenario):
    """Executed before each scenario"""
    # You can reset state here if needed
    pass


def after_scenario(context, scenario):
    """Executed after each scenario"""
    if scenario.status == "failed":
        # Save screenshot on failure
        screenshot_name = f"screenshot_{scenario.name.replace(' ', '_')}.png"
        context.browser.save_screenshot(screenshot_name)
        print(f"Screenshot saved to {screenshot_name}")


def after_all(context):
    """Executed once after all tests"""
    if hasattr(context, "browser"):
        context.browser.quit()


# ============= EOF =============================================
