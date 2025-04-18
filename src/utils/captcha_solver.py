import logging
import base64
from twocaptcha import TwoCaptcha  # From 2captcha-python
from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import (
    RecaptchaV2ProxylessRequest,
    ImageToTextRequest,
)
from src.config.config import (
    CAPTCHA_API_KEY_2CAPTCHA,
    CAPTCHA_API_KEY_CAPMONSTER,
    CAPTCHA_SERVICE,
)
from src.models.imei_models import CaptchaSolution

logger = logging.getLogger(__name__)


class CaptchaSolver:
    """Utility class to solve captchas using either 2Captcha or CapMonster."""

    def __init__(self, service=None):
        """Initialize the captcha solver with the specified service."""
        self.service = service or CAPTCHA_SERVICE
        if self.service == "2captcha":
            self.solver = TwoCaptcha(CAPTCHA_API_KEY_2CAPTCHA)
        elif self.service == "capmonster":
            client_options = ClientOptions(api_key=CAPTCHA_API_KEY_CAPMONSTER)
            self.solver = CapMonsterClient(options=client_options)
        else:
            raise ValueError(f"Unsupported captcha service: {self.service}")

    async def solve_image_captcha(
        self, base64_image=None, image_path=None, site_key=None, page_url=None
    ):
        """
        Solve an image captcha using the configured service.

        Args:
            base64_image: Base64-encoded image
            image_path: Path to image file
            site_key: For reCAPTCHA/hCaptcha
            page_url: For reCAPTCHA/hCaptcha

        Returns:
            CaptchaSolution object with the solution or error
        """
        try:
            if self.service == "2captcha":
                return await self._solve_with_2captcha(
                    base64_image, image_path, site_key, page_url
                )
            elif self.service == "capmonster":
                return await self._solve_with_capmonster(
                    base64_image, image_path, site_key, page_url
                )
        except Exception as e:
            logger.error(f"Error solving captcha: {str(e)}")
            return CaptchaSolution(solution="", error=str(e), success=False)

    async def _solve_with_2captcha(
        self, base64_image=None, image_path=None, site_key=None, page_url=None
    ):
        """Solve captcha with 2Captcha."""
        try:
            if base64_image:
                result = self.solver.normal(base64_image)
            elif image_path:
                result = self.solver.normal(image_path)
            elif site_key and page_url:
                # Added invisible=1 parameter to handle invisible reCAPTCHA
                result = self.solver.recaptcha(
                    sitekey=site_key,
                    url=page_url,
                    invisible=1,  # Set to 1 for invisible reCAPTCHA
                )
            else:
                raise ValueError(
                    "Either base64_image, image_path, or (site_key and page_url) must be provided"
                )

            return CaptchaSolution(
                solution=result["code"],
                captcha_id=result.get("captchaId", ""),
                success=True,
            )
        except Exception as e:
            return CaptchaSolution(solution="", error=str(e), success=False)

    async def _solve_with_capmonster(
        self, base64_image=None, image_path=None, site_key=None, page_url=None
    ):
        """Solve captcha with CapMonster."""
        try:
            if base64_image or image_path:
                # For image captcha
                image_data = None
                if base64_image:
                    image_data = base64_image
                elif image_path:
                    with open(image_path, "rb") as f:
                        image_data = base64.b64encode(f.read()).decode("utf-8")

                if not image_data:
                    raise ValueError("Failed to get image data from provided sources")

                # Create the image to text request
                image_request = ImageToTextRequest(body=image_data)

                # Solve the captcha
                solution = await self.solver.solve_captcha(image_request)

                return CaptchaSolution(
                    solution=solution.get("text", ""),
                    captcha_id=str(solution.get("taskId", "")),
                    success=True,
                )

            elif site_key and page_url:
                # For reCAPTCHA
                recaptcha_request = RecaptchaV2ProxylessRequest(
                    websiteUrl=page_url,
                    websiteKey=site_key,
                    isInvisible=True,  # Added support for invisible reCAPTCHA
                )

                # Solve the captcha
                solution = await self.solver.solve_captcha(recaptcha_request)

                return CaptchaSolution(
                    solution=solution.get("gRecaptchaResponse", ""),
                    captcha_id=str(solution.get("taskId", "")),
                    success=True,
                )
            else:
                raise ValueError(
                    "Either base64_image, image_path, or (site_key and page_url) must be provided"
                )
        except Exception as e:
            return CaptchaSolution(solution="", error=str(e), success=False)
