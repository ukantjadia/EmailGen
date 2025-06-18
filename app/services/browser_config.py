# from playwright.async_api import async_playwright
# from playwright_stealth import stealth_async

# class PlaywrightManager:
#     def __init__(self, headless: bool = True):
#         self.headless = headless
#         self.playwright = None
#         self.browser = None
#         self.context = None
#         self.page = None

#     async def start_browser(self, stealth_on: bool, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"):
#         """Initialize the Playwright session and start the browser."""
#         self.playwright = await async_playwright().start()
#         self.browser = await self.playwright.chromium.launch(headless=self.headless,
#                                                              args= ['--disable-dev-shm-usage'])
#         self.context = await self.browser.new_context(
#             viewport={"width": 1920, "height": 1080},
#             user_agent=user_agent,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#             bypass_csp=True,
#             locale='en-US',
#         )
#         self.page = await self.context.new_page()
#         if stealth_on:
#             await stealth_async(self.page)
#         return self.page

#     async def new_page(self, stealth_on: bool = False, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"):
#         self.context = await self.browser.new_context(
#             viewport={"width": 1920, "height": 1080},
#             user_agent=user_agent,
#             java_script_enabled=True,
#             ignore_https_errors=True,
#             bypass_csp=True,
#             locale='en-US',
#         )
#         page = await self.context.new_page()
#         if stealth_on:
#             await stealth_async(page)
#         return page

#     async def stop_browser(self):
#         """Close the browser and stop the Playwright session."""
#         if self.page:
#             await self.page.close()
#             self.page = None
#         if self.context:
#             await self.context.close()
#             self.context = None
#         if self.browser:
#             await self.browser.close()
#             self.browser = None
#         if self.playwright:
#             await self.playwright.stop()
#             self.playwright = None