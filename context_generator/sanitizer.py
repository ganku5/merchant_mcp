from pathlib import Path
import re


def sanitize_markdown(markdown_path: str) -> str:
    p = Path(markdown_path)
    s = p.read_text(errors="ignore")

    replacements = {
        '| HTTP method | Not confirmed from provided evidence (typically `POST` for a registration operation) |':
            '| HTTP method | To be confirmed with Juspay integration team |',

        '| HTTP method | Not confirmed from provided evidence |':
            '| HTTP method | To be confirmed with Juspay integration team |',

        '| Full URL | Not confirmed from provided evidence |':
            '| Full URL | To be shared during merchant onboarding |',

        'the API version is resolved from the incoming request (likely via an `x-api-version` header).':
            'the API version is resolved from the incoming request. Exact header/query name is shared during integration onboarding.',

        'Exact header/query name is not confirmed from provided evidence.':
            'Exact header/query name is shared during integration onboarding.',

        'Not confirmed from provided evidence':
            'To be confirmed with Juspay integration team',

        'not confirmed from the provided evidence':
            'to be confirmed with Juspay integration team',

        'not confirmed from provided evidence':
            'to be confirmed with Juspay integration team',

        '"flow": "COLLECT"':
            '"flow": "TRANSACTION"',

        '"status": "SUCCESS",\n  "responseCode": "00",\n  "responseMessage": "Intent registered successfully",\n  "payload": {\n    "_comment": "Exact payload fields are To be confirmed with Juspay integration team"\n  },':
            '"status": "To be confirmed with Juspay integration team",\n  "responseCode": "To be confirmed with Juspay integration team",\n  "responseMessage": "To be confirmed with Juspay integration team",\n  "payload": {\n    "_comment": "Exact payload fields are shared during integration onboarding"\n  },',

        '> The values for `status`, `responseCode`, and `responseMessage` above are illustrative examples. Actual values are returned by the platform.':
            '> Exact success status, response code, response message, and payload shape are shared during integration onboarding.',
    }

    for old, new in replacements.items():
        s = s.replace(old, new)

    # Remove internal evidence section from merchant-facing markdown.
    s = re.sub(r"\n## Evidence Used\n(.|\n)*$", "\n", s)

    # Remove markdown comments that sound like internal placeholders.
    s = s.replace('_comment', 'note')

    p.write_text(s)
    return str(p)
