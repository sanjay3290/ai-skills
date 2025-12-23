# Imagen Skill - Usage Examples

## Frontend Development Scenarios

### Hero Image for Landing Page
```
User: "I need a hero image for my fintech startup landing page"

Claude will run:
python scripts/generate_image.py "Modern fintech hero image with abstract flowing gradients in blue and purple, suggesting financial growth and technology, clean minimalist style" "./src/assets/hero.png"
```

### App Icons
```
User: "Generate an app icon for my weather app"

Claude will run:
python scripts/generate_image.py --size 512 "Minimalist weather app icon, stylized sun partially behind a cloud, warm orange and blue gradient, rounded square suitable for iOS/Android" "./assets/icons/weather-icon.png"
```

### Placeholder Images
```
User: "I need placeholder images for my e-commerce product grid"

Claude will run:
python scripts/generate_image.py "E-commerce product placeholder image, neutral gray background, subtle product box outline, professional and clean" "./public/images/placeholder-product.png"
```

### Background Patterns
```
User: "Create a subtle background pattern for my website"

Claude will run:
python scripts/generate_image.py --size 2K "Seamless tileable subtle geometric pattern, very light gray on white, minimalist, suitable for website background" "./assets/bg-pattern.png"
```

## Documentation & Diagrams

### Architecture Diagram
```
User: "Visualize our microservices architecture"

Claude will run:
python scripts/generate_image.py "Clean technical diagram showing microservices architecture, boxes connected by arrows, services labeled API Gateway, Auth Service, User Service, Order Service, white background, professional style" "./docs/images/architecture.png"
```

### Process Flowchart
```
User: "Create a flowchart for user onboarding"

Claude will run:
python scripts/generate_image.py "Flowchart diagram showing user onboarding process, start with signup, branches for email verification, profile setup, tutorial completion, clean business style with blue accents" "./docs/onboarding-flow.png"
```

## Marketing & Creative

### Social Media Graphics
```
User: "I need a banner for our product launch on Twitter"

Claude will run:
python scripts/generate_image.py "Modern product launch banner 1200x675, bold typography space for text overlay, dynamic abstract tech background, vibrant gradients purple to blue" "./marketing/twitter-banner.png"
```

### Blog Post Headers
```
User: "Generate a header image for my blog post about AI"

Claude will run:
python scripts/generate_image.py "Blog header image about artificial intelligence, abstract neural network visualization, glowing nodes and connections, dark background with blue accent lights, futuristic and professional" "./blog/images/ai-header.png"
```

## Professional Photography (Advanced Techniques)

### Corporate Headshots
```
User: "Generate a professional corporate headshot for our team page"

Claude will run:
python scripts/generate_image.py "Professional corporate headshot, 85mm f/2.8 lens, three-point studio lighting with soft key light from left, subtle fill light, rim light for hair separation, navy blue business suit, neutral gray backdrop, visible catchlights in eyes, chest-up framing, natural skin texture with subtle pores, sharp focus on eyes" "./team/headshot-template.png"
```

### Casual Lifestyle Portraits
```
User: "Create a casual, authentic-looking portrait for my personal brand"

Claude will run:
python scripts/generate_image.py "Casual lifestyle portrait, Kodak Portra 400 color tones, natural window light with soft shadows, 3/4 body shot, authentic film grain, early-2000s digital camera aesthetic, relaxed pose, natural skin texture, warm highlights, slight background blur" "./branding/casual-portrait.png"
```

### High-Fashion Editorial
```
User: "Generate a high-fashion editorial style photo"

Claude will run:
python scripts/generate_image.py "High-fashion editorial portrait, dramatic studio lighting with strong key light, deep shadows, 85mm f/1.4 lens with shallow depth of field, model wearing designer clothing, fabric texture visible, silk sheen and drape, backstage atmosphere, bold composition, magazine-quality, keep facial features exactly consistent" "./fashion/editorial-shot.png"
```

### Product Photography with Model
```
User: "Create a lifestyle product shot showing someone using headphones"

Claude will run:
python scripts/generate_image.py "Lifestyle product photography, person wearing premium over-ear headphones, 50mm prime lens, natural soft lighting from large window, clean modern interior background with bokeh, 3/4 profile view, natural skin texture, subtle catchlights, product details sharp and visible, authentic lifestyle feel, Fujifilm Pro 400H color tones" "./products/headphones-lifestyle.png"
```

### Social Media Selfie Style
```
User: "Generate an authentic-looking selfie for social media content"

Claude will run:
python scripts/generate_image.py "Authentic social media selfie, iPhone camera quality with realistic sensor noise, bathroom mirror selfie angle, natural indoor lighting, slight lens distortion, casual outfit, natural skin with subtle imperfections, relaxed authentic expression, 1990s disposable camera aesthetic, do not alter the face, early morning soft light" "./content/selfie-style.png"
```

### E-commerce Fashion
```
User: "Create a product photo for an e-commerce clothing listing"

Claude will run:
python scripts/generate_image.py "E-commerce fashion photography, model wearing casual cotton t-shirt, clean white studio background, soft even lighting, full body shot, fabric texture clearly visible, natural pose, 70mm lens, product colors accurate, subtle shadows for depth, professional catalog style, natural skin texture" "./ecommerce/tshirt-listing.png"
```

## Command Line Usage

```bash
# Generate with default settings
python scripts/generate_image.py "A peaceful zen garden"

# Specify output location
python scripts/generate_image.py "Mountain landscape" "./wallpapers/mountains.png"

# High resolution output
python scripts/generate_image.py --size 2K "Detailed cityscape" "./high-res/city.png"

# Quick thumbnail/icon
python scripts/generate_image.py --size 512 "Simple checkmark icon" "./icons/check.png"
```

### Windows PowerShell

```powershell
# Generate with default settings
python scripts/generate_image.py "A peaceful zen garden"

# With environment variable for size
$env:IMAGE_SIZE = "2K"
python scripts/generate_image.py "Detailed cityscape" "./high-res/city.png"
```

### Batch Generation (via shell)

**macOS/Linux:**
```bash
# Generate multiple variations
for i in 1 2 3; do
    python scripts/generate_image.py "Abstract art variation $i" "./art/abstract-$i.png"
done
```

**Windows PowerShell:**
```powershell
# Generate multiple variations
1..3 | ForEach-Object {
    python scripts/generate_image.py "Abstract art variation $_" "./art/abstract-$_.png"
}
```

## Integration with Frontend Workflow

### React Project
```
User: "Add a loading spinner image to my React components"

Claude will:
1. Generate the image: python scripts/generate_image.py "Minimal loading spinner, circular design, gradient from light to dark blue, clean vector style" "./src/assets/spinner.png"
2. Update component to use the new image
```

### Vue Project
```
User: "Need an empty state illustration for when there's no data"

Claude will:
1. Generate: python scripts/generate_image.py "Friendly empty state illustration, person looking at empty box, soft pastel colors, friendly and approachable, modern SaaS style" "./src/assets/empty-state.png"
2. Add to the component template
```

### Flutter Project
```
User: "Generate an onboarding illustration"

Claude will:
1. Generate: python scripts/generate_image.py --size 2K "Mobile app onboarding illustration, person using smartphone, abstract flowing shapes in background, modern gradient style" "./assets/images/onboarding.png"
2. Add to pubspec.yaml assets
3. Use in the onboarding widget
```

## Tips for Better Results

### Basic Tips
1. **Be Descriptive**: The more detail, the better the output
2. **Mention Style**: "flat design", "3D render", "watercolor", "minimalist"
3. **Specify Colors**: "blue and orange gradient", "monochrome", "pastel colors"
4. **Include Context**: "suitable for dark mode", "web-safe", "mobile app"
5. **Define Purpose**: "for hero section", "app icon", "documentation"

### Advanced Photography Tips
6. **Specify Camera Settings**: "85mm f/1.4 lens", "50mm prime", "shallow depth of field"
7. **Define Lighting Setup**: "three-point lighting", "soft key light from left", "rim light for separation"
8. **Reference Film Stocks**: "Kodak Portra 400 tones", "Fujifilm Pro 400H", "subtle film grain"
9. **Add Era Aesthetics**: "1990s disposable camera quality", "early-2000s digital look"
10. **Include Texture Details**: "natural skin texture with visible pores", "fabric weave visible"
11. **Specify Framing**: "chest-up framing", "3/4 body shot", "rule of thirds placement"
12. **Preserve Faces**: When editing, add "keep facial features exactly consistent" or "do not alter the face"
