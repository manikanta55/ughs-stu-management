"""Verify the Claude API key in backend/.env works: `uv run python -m scripts.check_llm`."""

import sys

import anthropic

from app.config import get_settings


def main() -> int:
    settings = get_settings()
    if settings.anthropic_api_key is None:
        print("ANTHROPIC_API_KEY is not set in backend/.env")
        return 1

    # Settings reads .env itself (it isn't exported to os.environ), so pass the key explicitly.
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    try:
        model = client.models.retrieve(settings.anthropic_model)
        print(f"Key accepted. Model available: {model.display_name} ({model.id})")

        # A tiny real request, to confirm the account has usable credits.
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
    except anthropic.AuthenticationError:
        print("Invalid API key (401). Re-copy it from the Claude Console.")
        return 1
    except anthropic.PermissionDeniedError as e:
        print(f"Key lacks permission (403): {e.message}")
        return 1
    except anthropic.NotFoundError:
        print(f"Model '{settings.anthropic_model}' not found for this key.")
        return 1
    except anthropic.BadRequestError as e:
        # Out-of-credit accounts are rejected with a 400 that mentions the credit balance.
        print(f"Request rejected (400): {e.message}")
        return 1
    except anthropic.RateLimitError:
        print("Rate limited (429). Try again in a minute.")
        return 1
    except anthropic.APIStatusError as e:
        print(f"API error {e.status_code}: {e.message}")
        return 1
    except anthropic.APIConnectionError:
        print("Could not reach the Claude API (network/proxy issue).")
        return 1

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    usage = response.usage
    print(
        f"Test message OK: reply={text!r}, stop_reason={response.stop_reason}, "
        f"tokens in/out={usage.input_tokens}/{usage.output_tokens}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
