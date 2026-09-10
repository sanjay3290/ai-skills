# Imagen - AI Image Generation Skill

A Claude Code skill that generates images using Google Gemini's image generation model. Simply ask Claude to create an image during any coding session, and it will generate and save it for you.

**Cross-Platform**: Works on Windows, macOS, and Linux.

## Quick Start

### 1. Install the Skill

```bash
# Via plugin marketplace (recommended)
/plugin install imagen@ai-skills

# Or add the entire marketplace
/plugin marketplace add sanjay3290/ai-skills
```

### 2. Set Your API Key

Get a free API key from [Google AI Studio](https://aistudio.google.com/):

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY = "your-api-key-here"
```

**Windows (CMD):**
```cmd
set GEMINI_API_KEY=your-api-key-here
```

**macOS/Linux:**
```bash
export GEMINI_API_KEY="your-api-key-here"

# Add to ~/.zshrc or ~/.bashrc to persist
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.zshrc
```

### 3. Use It!

Just ask Claude to generate an image during any conversation:

```
"Generate an image of a sunset over mountains"
"I need a hero image for my landing page"
"Create an app icon for a weather app"
```

## How It Works

When you mention needing an image, Claude will automatically:
1. Recognize the request and activate this skill
2. Call the Google Gemini API with your prompt
3. Save the generated image to your project
4. Tell you where to find it

## Features

- **Cross-Platform**: Python script works on Windows, macOS, and Linux
- **Automatic Activation**: Claude detects when you need an image
- **Multiple Sizes**: 512px, 1K (default), or 2K resolution
- **Custom Output Paths**: Save images wherever you need them
- **Frontend Ready**: Perfect for UI development, placeholders, icons
- **Documentation Images**: Generate diagrams, illustrations, flowcharts

## Usage Examples

### During Frontend Development
```
You: "I'm building a dashboard. Generate a placeholder chart image."
Claude: *generates and saves image* "Created the image at ./assets/chart-placeholder.png"
```

### For Documentation
```
You: "Create an architecture diagram for our microservices"
Claude: *generates image* "Saved to ./docs/architecture.png"
```

### Custom Size & Location
```
You: "Generate a high-res hero image and save it to ./public/hero.png"
Claude: *generates 2K image at specified path*
```

## Configuration

Gemini remains the default provider. To opt into Atlas Cloud, set `ATLASCLOUD_API_KEY` and pass `--provider atlas`; the Atlas path validates the live model catalog, submits generation once without POST retries, and uses bounded retries only while polling prediction status.

```bash
export ATLASCLOUD_API_KEY="your-api-key-here"
python scripts/generate_image.py --provider atlas --aspect 16:9 \
  "A clean architecture diagram" "./architecture.png"
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Gemini only | - | Your Google Gemini API key |
| `IMAGE_SIZE` | No | `1K` | Default size (512, 1K, or 2K) |
| `GEMINI_MODEL` | No | `gemini-3-pro-image-preview` | Gemini model ID |
| `ATLASCLOUD_API_KEY` | Atlas only | - | Atlas Cloud API key |
| `ATLAS_IMAGE_MODEL` | No | `google/nano-banana-2-lite/text-to-image-developer` | Atlas Cloud image model ID |
| `IMAGE_PROVIDER` | No | `gemini` | Default provider (`gemini` or `atlas`) |

### Image Sizes

| Size | Resolution | Best For |
|------|------------|----------|
| `512` | 512x512 | Icons, thumbnails, quick previews |
| `1K` | 1024x1024 | General use, web images |
| `2K` | 2048x2048 | High-res, print, retina displays |

## Manual Script Usage

```bash
# Basic usage
python scripts/generate_image.py "A serene lake at dawn"

# Custom output path
python scripts/generate_image.py "App icon" "./icon.png"

# With size option
python scripts/generate_image.py --size 2K "Detailed landscape" "./wallpaper.png"

# With custom model
python scripts/generate_image.py --model gemini-3-pro-image-preview "A logo" "./logo.png"
```

## File Structure

```
imagen/
├── SKILL.md               # Skill definition (Claude reads this)
├── README.md              # This file
├── reference.md           # Detailed API reference
├── examples.md            # Usage examples
├── .env.example           # API key template
└── scripts/
    └── generate_image.py  # Cross-platform Python script
```

## Requirements

- **Python 3.6+**: No additional packages needed (uses standard library only)
- **Gemini API Key**: Free from [Google AI Studio](https://aistudio.google.com/)

## Troubleshooting

### "GEMINI_API_KEY not set"

**Windows:**
```powershell
echo $env:GEMINI_API_KEY  # Should show your key
```

**macOS/Linux:**
```bash
echo $GEMINI_API_KEY  # Should show your key
source ~/.zshrc       # Reload if you just added it
```

### API Errors
- **400**: Check your prompt for special characters
- **429**: Rate limited, wait and retry
- **403**: Invalid API key

## Getting a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API Key" in the left sidebar
4. Create a new key or copy an existing one
5. Add it to your environment as shown above

## License

Apache-2.0 License - See [LICENSE](../../LICENSE) for details.
