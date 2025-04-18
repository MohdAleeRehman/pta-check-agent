import logging
import asyncio
import base64
from typing import Dict, Any, Optional
from crewai import Task
from playwright.async_api import async_playwright, Browser, Page, ElementHandle
from src.agents.base_agent import BaseAgent
from src.config.config import PTA_URL
from src.models.imei_models import PTAVerificationResult

logger = logging.getLogger(__name__)


class PTACheckAgent(BaseAgent):
    """
    Agent responsible for navigating to the PTA website, entering IMEI,
    solving captcha, and retrieving the result.
    """

    def __init__(self, headless: bool = True, **kwargs):
        """
        Initialize the PTA Check Agent.

        Args:
            headless: Whether to use headless browser (invisible) or not
        """
        super().__init__(
            name="PTACheckAgent",
            description="Agent responsible for interacting with the PTA website",
            goal="Navigate the PTA website to check IMEI compliance status",
            backstory="I am an expert at web automation and browser interaction. "
            "I can navigate complex websites, fill forms, and extract data accurately.",
            **kwargs,
        )
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    def create_check_task(self) -> Task:
        """
        Create a task for checking IMEI on the PTA website.

        Returns:
            Task object for PTA IMEI check
        """
        return Task(
            description="Check IMEI compliance status on the PTA website",
            expected_output="IMEI compliance status (Compliant or Non-Compliant) or error",
            agent=self.get_agent(),
            # Removed context and async_execution parameters
        )

    async def launch_browser(self) -> None:
        """Launch the browser if not already launched."""
        if not self.browser:
            self.log_info("Launching browser")
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720}
            )
            self.page = await self.context.new_page()
            self.log_info("Browser launched successfully")

    async def close_browser(self) -> None:
        """Close the browser if it's open."""
        if self.browser:
            self.log_info("Closing browser")
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
            self.log_info("Browser closed successfully")

    async def navigate_to_pta_site(self) -> bool:
        """
        Navigate to the PTA DIRBS website.

        Returns:
            True if navigation was successful, False otherwise
        """
        try:
            self.log_info(f"Navigating to PTA website: {PTA_URL}")
            await self.launch_browser()

            # Navigate to PTA website
            await self.page.goto(PTA_URL, wait_until="networkidle")

            # Check if page loaded successfully
            if not self.page.url.startswith(PTA_URL):
                self.log_error(
                    f"Failed to navigate to PTA website. Current URL: {self.page.url}"
                )
                return False

            self.log_info("Successfully navigated to PTA website")
            return True
        except Exception as e:
            self.log_error(f"Error navigating to PTA website: {str(e)}")
            return False

    async def capture_captcha_image(self) -> Optional[Dict[str, Any]]:
        """
        Detect and handle captcha on the PTA website.
        Can handle both traditional image captchas and reCAPTCHA v2.

        Returns:
            Dictionary with captcha info or None if failed
        """
        try:
            # First, check if there's a standard image captcha
            captcha_img_selector = "img#captchaimg"
            recaptcha_selector = "iframe[title='reCAPTCHA']"

            self.log_info("Checking for captcha type...")

            # Wait a moment for page to fully load
            await asyncio.sleep(2)

            # Check for traditional image captcha
            has_img_captcha = (
                await self.page.query_selector(captcha_img_selector) is not None
            )

            # Check for reCAPTCHA
            has_recaptcha = (
                await self.page.query_selector(recaptcha_selector) is not None
            )

            self.log_info(
                f"Captcha detection: Image captcha: {has_img_captcha}, reCAPTCHA: {has_recaptcha}"
            )

            # Handle image captcha
            if has_img_captcha:
                self.log_info("Traditional image captcha detected")
                await self.page.wait_for_selector(
                    captcha_img_selector, state="visible", timeout=5000
                )

                # Get the captcha element
                captcha_elem = await self.page.query_selector(captcha_img_selector)
                if not captcha_elem:
                    self.log_error("Captcha image element not found")
                    return None

                # Get the image as base64
                captcha_base64 = await self.page.evaluate(
                    """(element) => {
                    const canvas = document.createElement('canvas');
                    const context = canvas.getContext('2d');
                    canvas.width = element.width;
                    canvas.height = element.height;
                    context.drawImage(element, 0, 0);
                    return canvas.toDataURL('image/png').split(',')[1];
                }""",
                    captcha_elem,
                )

                if not captcha_base64:
                    self.log_error("Failed to capture captcha as base64")
                    return None

                self.log_info("Successfully captured image captcha")
                return {"type": "image_captcha", "data": captcha_base64}

            # Handle reCAPTCHA
            elif has_recaptcha:
                self.log_info("reCAPTCHA v2 detected")

                # Get site key
                site_key = await self.page.evaluate(
                    """() => {
                    const recaptchaElement = document.querySelector('.g-recaptcha');
                    return recaptchaElement ? recaptchaElement.getAttribute('data-sitekey') : null;
                }"""
                )

                if not site_key:
                    self.log_error("Failed to extract reCAPTCHA site key")
                    return None

                self.log_info(f"Extracted reCAPTCHA site key: {site_key}")

                return {
                    "type": "recaptcha",
                    "data": site_key,
                    "page_url": self.page.url,
                }

            # No recognized captcha found
            else:
                # Some sites might not show captcha immediately or might bypass it sometimes
                self.log_info("No recognized captcha detected on the page")

                # Check if we might have already passed a captcha step or if it's not showing
                # Look for the IMEI input field to verify we're on the right page - using updated selector
                imei_input = await self.page.query_selector("input#imei")
                if imei_input:
                    self.log_info(
                        "IMEI input field found - page appears to be ready without captcha"
                    )
                    return {"type": "no_captcha", "data": None}
                else:
                    self.log_error("Page doesn't seem to be in the expected state")

                    # Take a screenshot for debugging
                    screenshot = await self.page.screenshot(type="jpeg", quality=50)
                    screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")

                    return {
                        "type": "error",
                        "data": screenshot_b64,
                        "message": "Unexpected page state - couldn't find captcha or IMEI input",
                    }

        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error detecting/capturing captcha: {error_message}")
            return None

    async def enter_imei_and_captcha(self, imei: str, captcha_solution: str) -> bool:
        """
        Enter the IMEI and captcha solution on the PTA website.

        Args:
            imei: The IMEI number to check
            captcha_solution: The solution to the captcha

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find IMEI input field
            imei_selector = "input#imei"

            # Enter IMEI
            self.log_info(f"Entering IMEI: {imei}")
            await self.page.fill(imei_selector, imei)

            # Check if we're dealing with a reCAPTCHA solution
            if captcha_solution and len(captcha_solution) > 50:
                self.log_info("Detected reCAPTCHA solution token, injecting into page")
                
                # Take a screenshot before injection for debugging
                try:
                    before_screenshot = await self.page.screenshot(type="jpeg", quality=50)
                    self.log_info("Took before-injection screenshot for debugging")
                except Exception:
                    self.log_info("Failed to take before-injection screenshot")
                
                # Inject the reCAPTCHA solution token directly into the textarea that's already present in PTA's page
                injection_result = await self.page.evaluate(f"""() => {{
                    try {{
                        // Find the g-recaptcha-response textarea directly
                        let responseElement = document.querySelector('textarea.g-recaptcha-response');
                        
                        if (!responseElement) {{
                            // Fallback to ID-based lookup if class-based doesn't work
                            responseElement = document.getElementById('g-recaptcha-response');
                        }}
                        
                        if (!responseElement) {{
                            // If still not found, create it
                            responseElement = document.createElement('textarea');
                            responseElement.id = 'g-recaptcha-response';
                            responseElement.name = 'g-recaptcha-response';
                            responseElement.className = 'g-recaptcha-response';
                            responseElement.style.display = 'none';
                            
                            // Find the reCAPTCHA container and add our response element
                            const recaptchaDiv = document.querySelector('.g-recaptcha');
                            if (recaptchaDiv) {{
                                recaptchaDiv.appendChild(responseElement);
                            }} else {{
                                document.body.appendChild(responseElement);
                            }}
                        }}
                        
                        // Set the value
                        responseElement.value = '{captcha_solution}';
                        responseElement.innerHTML = '{captcha_solution}';
                        
                        // Log for debugging
                        console.log('reCAPTCHA response injected');
                        
                        // Try to find and call the callback directly
                        let callbackResult = null;
                        try {{
                            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                                const keys = Object.keys(___grecaptcha_cfg.clients);
                                if (keys.length > 0) {{
                                    const client = ___grecaptcha_cfg.clients[keys[0]];
                                    const clientKeys = Object.keys(client);
                                    for (const key of clientKeys) {{
                                        if (typeof client[key].callback === 'function') {{
                                            client[key].callback('{captcha_solution}');
                                            callbackResult = 'Called direct callback';
                                            break;
                                        }}
                                    }}
                                }}
                            }}
                        }} catch (cbError) {{
                            callbackResult = 'Callback error: ' + cbError.toString();
                        }}
                        
                        return {{ 
                            success: true, 
                            injectedTo: responseElement ? responseElement.id : 'not-found',
                            callbackResult: callbackResult
                        }};
                    }} catch (e) {{
                        return {{ success: false, error: e.toString() }};
                    }}
                }}""")
                
                self.log_info(f"reCAPTCHA injection result: {injection_result}")
                
            else:
                # Handle traditional image captcha
                captcha_selector = "input#txtCaptcha"
                self.log_info(f"Entering captcha solution: {captcha_solution}")
                await self.page.fill(captcha_selector, captcha_solution)
                
            # Wait a moment for any reCAPTCHA callbacks to complete
            await asyncio.sleep(1)

            return True
        except Exception as e:
            self.log_error(f"Error entering IMEI and captcha: {str(e)}")
            return False

    async def click_check_button(self) -> bool:
        """
        Click the 'Check' button on the PTA website.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use the specific button selector from the PTA website
            check_button_selector = "button#submit.btn.btn-medium.btn--green"
            
            self.log_info(f"Clicking the Check button using selector: {check_button_selector}")
            
            # Wait for the button to be visible and clickable
            await self.page.wait_for_selector(check_button_selector, state="visible", timeout=5000)
            
            # Click the button
            await self.page.click(check_button_selector)
            self.log_info("Successfully clicked the Check button")
            
            # Wait for result to load
            await self.page.wait_for_load_state("networkidle")
            
            return True
            
        except Exception as e:
            self.log_error(f"Error with primary button selector: {str(e)}")
            
            # Fall back to the robust selector approach if the specific one fails
            try:
                # Use alternative selectors as fallbacks
                fallback_selectors = [
                    "button#submit",                     # ID only
                    "button[name='submit']",             # name attribute
                    "button.btn-medium.btn--green",      # classes
                    "button:has-text('Check')",          # Text content
                    "button:has(span.text:has-text('Check'))"  # Nested span with text
                ]
                
                for selector in fallback_selectors:
                    try:
                        self.log_info(f"Trying fallback selector: {selector}")
                        check_button = await self.page.wait_for_selector(
                            selector, state="visible", timeout=2000
                        )
                        if check_button:
                            await check_button.click()
                            self.log_info(f"Successfully clicked button with selector: {selector}")
                            await self.page.wait_for_load_state("networkidle")
                            return True
                    except Exception:
                        continue
                
                # If we get here, try to submit the form directly
                self.log_info("Attempting to submit the form directly...")
                await self.page.evaluate("""() => {
                    const forms = document.querySelectorAll('form');
                    if (forms.length > 0) {
                        forms[0].submit();
                        return true;
                    }
                    return false;
                }""")
                await self.page.wait_for_load_state("networkidle")
                return True
                
            except Exception as form_error:
                self.log_error(f"Error submitting form: {str(form_error)}")
                return False
                
        except Exception as e:
            self.log_error(f"Error clicking check button: {str(e)}")
            return False

    async def extract_result(self, imei: str) -> PTAVerificationResult:
        """
        Extract the verification result from the page.

        Args:
            imei: The IMEI being checked

        Returns:
            PTAVerificationResult object with status and details
        """
        try:
            # Give some time for results to render
            await asyncio.sleep(1)

            # Find result elements based on the actual HTML structure of the results page
            self.log_info("Looking for result content...")
            
            # Wait for the article containing the result to appear
            result_container_selector = "article.dirbs-banner"
            
            try:
                await self.page.wait_for_selector(
                    result_container_selector, state="visible", timeout=10000
                )
                self.log_info("Found result container")
                
                # Get the text content of the paragraph containing the result
                result_text_selector = "article.dirbs-banner p.text"
                result_text = await self.page.text_content(result_text_selector)
                
                if not result_text:
                    self.log_error("Result element found but no text content")
                    return PTAVerificationResult(
                        imei=imei,
                        status="Error",
                        error_message="Could not extract result text",
                    )

                # Get the image URL to determine status
                result_image_selector = "article.dirbs-banner img"
                image_src = await self.page.evaluate("""(selector) => {
                    const img = document.querySelector(selector);
                    return img ? img.getAttribute('src') : null;
                }""", result_image_selector)

                # Process the result
                result_text = result_text.strip()
                self.log_info(f"Raw result text: {result_text}")
                self.log_info(f"Result image: {image_src}")

                # Set the default status
                status = "Unknown"
                
                # Determine compliance status based on the image and text
                if image_src and "ok_512.png" in image_src:
                    status = "Compliant"
                elif image_src and "blocked_512.png" in image_src:
                    status = "Non-Compliant"
                # Text-based fallback determination
                elif "valid/compliant" in result_text.lower():
                    status = "Compliant"
                elif "not been paid" in result_text.lower() or "non-compliant" in result_text.lower():
                    status = "Non-Compliant"
                
                # Extract additional details like device model
                details = {"raw_text": result_text}
                
                # Try to extract device model information
                device_model_match = None
                
                # Look for device information in quotation marks
                import re
                device_model_pattern = r'"([^"]+)"'
                device_model_match = re.search(device_model_pattern, result_text)
                
                # If not found in quotes, try the common pattern
                if not device_model_match:
                    device_model_pattern = r'This IMEI is of (.*?) device'
                    device_model_match = re.search(device_model_pattern, result_text)
                
                if device_model_match:
                    details["device_model"] = device_model_match.group(1)
                    self.log_info(f"Extracted device model: {details['device_model']}")

                # Take a screenshot of the result for reference
                try:
                    screenshot = await self.page.screenshot(type="jpeg", quality=50)
                    screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")
                    details["result_screenshot"] = screenshot_b64
                except Exception as screenshot_error:
                    self.log_error(f"Error capturing result screenshot: {str(screenshot_error)}")

                self.log_info(f"Extracted result status: {status}")
                return PTAVerificationResult(imei=imei, status=status, details=details)
                
            except Exception as selector_error:
                self.log_error(f"Error finding result elements: {str(selector_error)}")
                
                # Try a more generic approach - look for any text on the page that might contain result info
                try:
                    page_text = await self.page.evaluate("""() => {
                        return document.body.innerText;
                    }""")
                    
                    self.log_info("Attempting to extract result from page text")
                    
                    # Take a screenshot for debugging
                    screenshot = await self.page.screenshot(type="jpeg", quality=50)
                    screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")
                    
                    if "compliant" in page_text.lower() and imei in page_text:
                        self.log_info("Found compliant reference in page text")
                        if "non-compliant" in page_text.lower() or "not been paid" in page_text.lower():
                            return PTAVerificationResult(
                                imei=imei, 
                                status="Non-Compliant", 
                                details={
                                    "raw_text": page_text[:500], 
                                    "result_screenshot": screenshot_b64
                                }
                            )
                        else:
                            return PTAVerificationResult(
                                imei=imei, 
                                status="Compliant", 
                                details={
                                    "raw_text": page_text[:500], 
                                    "result_screenshot": screenshot_b64
                                }
                            )
                    
                    return PTAVerificationResult(
                        imei=imei,
                        status="Error",
                        error_message="Could not find result elements",
                        details={"page_text": page_text[:500], "result_screenshot": screenshot_b64}
                    )
                    
                except Exception as backup_error:
                    self.log_error(f"Error with backup result extraction: {str(backup_error)}")
                    
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error extracting result: {error_message}")
            return PTAVerificationResult(
                imei=imei, status="Error", error_message=error_message
            )

    async def check_imei(self, imei: str, captcha_solution: str) -> Dict[str, Any]:
        """
        Check IMEI status on the PTA website.

        Args:
            imei: The IMEI to check
            captcha_solution: The solution to the captcha

        Returns:
            Dictionary with check result
        """
        try:
            # Navigate to PTA site
            if not await self.navigate_to_pta_site():
                return {
                    "success": False,
                    "result": PTAVerificationResult(
                        imei=imei,
                        status="Error",
                        error_message="Failed to navigate to PTA website",
                    ).dict(),
                    "message": "Failed to navigate to PTA website",
                }

            # Enter IMEI and captcha
            if not await self.enter_imei_and_captcha(imei, captcha_solution):
                return {
                    "success": False,
                    "result": PTAVerificationResult(
                        imei=imei,
                        status="Error",
                        error_message="Failed to enter IMEI and captcha",
                    ).dict(),
                    "message": "Failed to enter IMEI and captcha",
                }

            # Click check button
            if not await self.click_check_button():
                return {
                    "success": False,
                    "result": PTAVerificationResult(
                        imei=imei,
                        status="Error",
                        error_message="Failed to click check button",
                    ).dict(),
                    "message": "Failed to click check button",
                }

            # Extract result
            result = await self.extract_result(imei)

            # Close browser
            await self.close_browser()

            if result.status == "Error":
                return {
                    "success": False,
                    "result": result.dict(),
                    "message": f"Error checking IMEI: {result.error_message}",
                }
            else:
                return {
                    "success": True,
                    "result": result.dict(),
                    "message": f"IMEI check completed successfully. Status: {result.status}",
                }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error checking IMEI: {error_message}")

            # Try to close browser
            await self.close_browser()

            return {
                "success": False,
                "result": PTAVerificationResult(
                    imei=imei, status="Error", error_message=error_message
                ).dict(),
                "message": f"Error checking IMEI: {error_message}",
            }

    async def get_captcha(self) -> Dict[str, Any]:
        """
        Navigate to the PTA website and get the captcha.

        Returns:
            Dictionary with captcha information
        """
        try:
            # Navigate to PTA site
            if not await self.navigate_to_pta_site():
                return {
                    "success": False,
                    "captcha_info": None,
                    "message": "Failed to navigate to PTA website",
                }

            # Detect and capture captcha
            captcha_info = await self.capture_captcha_image()
            if not captcha_info:
                return {
                    "success": False,
                    "captcha_info": None,
                    "message": "Failed to detect/capture captcha",
                }

            # Return appropriate response based on captcha type
            if captcha_info["type"] == "image_captcha":
                return {
                    "success": True,
                    "captcha_type": "image_captcha",
                    "captcha_image": captcha_info["data"],
                    "message": "Traditional image captcha captured successfully",
                }
            elif captcha_info["type"] == "recaptcha":
                return {
                    "success": True,
                    "captcha_type": "recaptcha",
                    "site_key": captcha_info["data"],
                    "page_url": captcha_info["page_url"],
                    "message": "reCAPTCHA detected, site key extracted successfully",
                }
            elif captcha_info["type"] == "no_captcha":
                return {
                    "success": True,
                    "captcha_type": "no_captcha",
                    "message": "No captcha needed - page appears ready for IMEI input",
                }
            else:
                # Error case
                return {
                    "success": False,
                    "captcha_type": "error",
                    "screenshot": captcha_info.get("data"),
                    "message": captcha_info.get(
                        "message", "Unknown captcha detection error"
                    ),
                }
        except Exception as e:
            error_message = str(e)
            self.log_error(f"Error getting captcha: {error_message}")

            # Try to close browser
            await self.close_browser()

            return {
                "success": False,
                "captcha_info": None,
                "message": f"Error getting captcha: {error_message}",
            }
