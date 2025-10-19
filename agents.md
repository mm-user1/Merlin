## Base rules for project:
Act as an experienced Python and Pinescript developer with trading and crypto algorithmic trading expertise.
IMPORTANT: Work strictly according to the given specifications. Any deviations are prohibited without my explicit consent.
IMPORTANT: The script must be maximally efficient and fast.
IMPORTANT: The GUI must use a light theme.

# UI Design Guidelines - Trading Backtester

## Core Design Principles

### Color Scheme - Strict Monochrome
All interface elements must use only grayscale colors. No colored elements permitted.

**Color Palette** (hex format for reference):
- **Background (viewport)**: `#e8e8e8` - light gray
- **Window background**: `#f5f5f5` - off-white
- **Title bar**: `#4a4a4a` - dark gray
- **Borders**: 
  - Primary: `#999999` (medium gray)
  - Secondary: `#bbbbbb` (light medium gray)
  - Tertiary: `#cccccc` (very light gray)
- **Text colors**: 
  - Primary text: `#2a2a2a` - near black
  - Secondary text: `#3a3a3a` - dark gray
  - Tertiary text: `#5a5a5a` - medium dark gray
  - Disabled/placeholder: `#777777` - medium gray
- **Interactive elements**:
  - Button primary: `#4a4a4a` background, `#ffffff` text
  - Button secondary: `#cccccc` background, `#2a2a2a` text
  - Button hover: `#3a3a3a` (primary), `#bbbbbb` (secondary)
  - Input fields: `#ffffff` background, `#999999` border
  - Input focus border: `#5a5a5a`
- **Container backgrounds**: `#e8e8e8`
- **Hover states**: `#dddddd`

**Critical Rule**: NO COLORS - strictly grayscale palette only.

### Typography
- **Font family**: Sans-serif system font (Segoe UI, Roboto, Helvetica, Arial)
- **Font sizes**:
  - Window title: 15px
  - Standard labels: 14px
  - Section headers: 12px (uppercase)
  - Input text: 14px
  - Small labels: 13px
- **Font weights**:
  - Section headers: 600 (semi-bold)
  - Title bar: 500 (medium)
  - Regular text: 400 (normal)
- **Text transforms**:
  - Section headers: UPPERCASE
  - All other text: Normal case

## Visual Hierarchy

### Window Structure
1. **Title Bar** (dark gray, top)
   - Application/window title (left-aligned)
   - Window controls: minimize, maximize, close (right-aligned)
   - Height: ~30-35px
   - Background: `#4a4a4a`
   - Text: white

2. **Content Area** (light background)
   - Padding: 20px all sides
   - Background: `#f5f5f5`
   - Single scrollable area (no tabs)

3. **Action Bar** (bottom)
   - Border-top separator
   - Buttons: Defaults (left), Cancel + Run (right)

### Layout Rules
- **Maximum width**: 800px
- **Window padding**: 20px
- **Section spacing**: 20px between major sections
- **Element spacing**: 10-12px between form elements
- **Compact spacing**: 8px within parameter groups

## Component Specifications

### 1. Section Headers
**Visual characteristics**:
- Text: 12px, uppercase, semi-bold (600 weight)
- Color: `#3a3a3a`
- Letter-spacing: 0.5px
- Bottom border: 1px solid `#bbbbbb`
- Padding-bottom: 6px
- Margin-bottom: 12px

**Usage**: Separate major sections (MA Settings, Risk Settings, Results)

### 2. Form Groups
**Standard horizontal layout**:
- Label + Input arranged horizontally
- Label width: ~120px (fixed)
- Input width: 100px (standard), 150px (dates), 80px (time/compact)
- Vertical spacing: 12px between rows
- Horizontal spacing: 10px between label and input

**Vertical layout** (for complex controls):
- Label on top
- Control below
- Spacing: 8px between label and control

### 3. Input Fields
**Specifications**:
- Background: white (`#ffffff`)
- Border: 1px solid `#999999`
- Border-radius: 3px
- Padding: 6px horizontal, 6px vertical
- Font-size: 14px
- Standard width: 100px
- Date width: 150px
- Time width: 80px
- Compact width: 70px

**Focus state**:
- Border color: `#5a5a5a` (darker gray)
- Optional subtle shadow: 2px blur, gray, low opacity

**Types required**:
- Text input (dates, times)
- Number input (integers and floats with step control)
- Checkbox (16×16px standard, 14×14px in MA selectors)

### 4. MA Type Selector (CRITICAL COMPONENT)
**Structure**: Checkbox grid for selecting moving average types

**Layout**:
- Container with white background and border
- Border: 1px solid `#999999`
- Padding: 8px
- Border-radius: 3px

**Checkbox arrangement** (2 rows × 6 columns):
- **Row 1**: ALL, EMA, SMA, HMA, WMA, ALMA
- **Row 2**: KAMA, TMA, T3, DEMA, VWMA, VWAP

**Checkbox specifications**:
- Size: 14×14px
- Spacing between options: 12px horizontal
- Spacing between rows: 4px vertical
- All checkboxes checked by default
- Label font-size: 13px
- Label position: right of checkbox

**Usage locations**:
1. T MA Type (in MA Settings section)
2. Trail MA Long (in Trailing Stops section)
3. Trail MA Short (in Trailing Stops section)

### 5. Buttons
**Primary button** (Run):
- Background: `#4a4a4a`
- Text color: `#ffffff`
- Hover: `#3a3a3a`
- Padding: 8px horizontal, 20px vertical
- Border-radius: 3px
- No border
- Font-size: 14px

**Secondary button** (Defaults, Cancel):
- Background: `#cccccc`
- Text color: `#2a2a2a`
- Hover: `#bbbbbb`
- Same dimensions as primary

**Special button** (Calendar):
- Background: `#dddddd`
- Border: 1px solid `#999999`
- Icon: 📅 (calendar emoji)
- Width: 40px
- Height: matches input field height

### 6. Collapsible Sections
**Purpose**: Group advanced/secondary options

**Visual design**:
- Container background: `#e8e8e8`
- Border: 1px solid `#bbbbbb`
- Border-radius: 3px

**Header** (clickable):
- Padding: 10px
- Display: arrow icon + uppercase section title
- Arrow icon: ▼ (10px, color `#5a5a5a`)
- Hover state: background `#dddddd`
- Cursor: pointer

**Content area**:
- Background: `#f5f5f5`
- Border-top: 1px solid `#bbbbbb` (separator from header)
- Padding: 10px
- Displayed when expanded

**Usage**:
- "STOPS AND FILTERS" section
- "TRAILING STOPS" section

### 7. Parameter Groups
**Purpose**: Compact inline display of related parameters

**Visual design**:
- Container with light background: `#e8e8e8`
- Border: 1px solid `#cccccc`
- Border-radius: 3px
- Padding: 8px horizontal, 12px vertical
- Margin-bottom: 8px

**Content layout**:
- Horizontal arrangement
- Label + Input pairs repeated
- Labels: minimal width (auto)
- Inputs: 70px width
- Spacing between pairs: 8px

**Examples**:
- "Stop Long X: [2] RR: [3] LP: [2]"
- "L Stop Max %: [3] S Stop Max %: [3]"

### 8. Results Area
**Specifications**:
- Background: `#e8e8e8`
- Border: 1px solid `#999999`
- Border-radius: 3px
- Minimum height: 200px
- Padding: 15px
- Font-style: italic (for placeholder text)
- Text color: `#777777` (placeholder), `#2a2a2a` (results)
- Placeholder: "Нажмите 'Run' для запуска бэктеста..."

## Required Interface Structure

### Complete Section Order:

#### 1. Date Filter Section
- [ ] Checkbox: "Date Filter" (checked by default)
- [ ] Checkbox: "Backtester" (checked by default)
- [ ] Start Date: [date input] [📅 button] [time input]
- [ ] End Date: [date input] [📅 button] [time input]

#### 2. MA Settings
- [ ] Label: "T MA Type"
- [ ] MA Selector (checkbox grid)
- [ ] Label: "Length" + Number input (default: 45)
- [ ] Label: "Close Count Long" + Number input (default: 7)
- [ ] Label: "Close Count Short" + Number input (default: 5)

#### 3. Stops and Filters (Collapsible)
- [ ] Parameter group: Stop Long X [2], RR [3], LP [2]
- [ ] Parameter group: Stop Short X [2], RR [3], LP [2]
- [ ] Parameter group: L Stop Max % [3], S Stop Max % [3]
- [ ] Parameter group: L Stop Max D [2], S Stop Max D [4]

#### 4. Trailing Stops (Collapsible)
- [ ] Parameter group: Trail RR Long [1], Trail RR Short [1]
- [ ] Label: "Trail MA Long"
- [ ] MA Selector (checkbox grid)
- [ ] Length [160], Offset [-1]
- [ ] Label: "Trail MA Short"
- [ ] MA Selector (checkbox grid)
- [ ] Length [160], Offset [1]

#### 5. Risk Settings
- [ ] Label: "Risk Per Trade" + Number input (default: 2, step: 0.01)
- [ ] Label: "Contract Size" + Number input (default: 0.01, step: 0.01)

#### 6. Results
- [ ] Section header: "RESULTS"
- [ ] Results display area (multiline text)

#### 7. Action Buttons
- [ ] Button: "Defaults" (secondary, left-aligned)
- [ ] Button: "Cancel" (secondary, right-aligned)
- [ ] Button: "Run" (primary, right-aligned)

## Spacing System

**Consistent spacing hierarchy**:
- **Large gap** (between major sections): 20px
- **Medium gap** (between form elements): 12px
- **Small gap** (within groups, label-to-input): 8-10px
- **Minimal gap** (between checkboxes in MA selector): 4px vertical, 12px horizontal
- **Window padding**: 20px all sides
- **Container padding**: 8-15px depending on component

## Border System

**Border widths**: All borders 1px
**Border colors by context**:
- Primary containers: `#999999`
- Section separators: `#bbbbbb`
- Parameter groups: `#cccccc`
- Title underlines: `#bbbbbb`

**Border radius**:
- Windows: 4px
- Inputs/buttons/containers: 3px

## Design Philosophy

1. **Monochrome aesthetic** - Professional, distraction-free interface using only grayscale
2. **No navigation chrome** - No tabs, no menu bar - direct access to all settings
3. **Clear visual hierarchy** - Title bar > Sections > Controls > Parameters
4. **Efficient space usage** - Compact parameter groups, collapsible advanced options
5. **Consistent spacing** - Predictable gaps create rhythm and readability
6. **Logical grouping** - Related settings grouped visually (borders, backgrounds)
7. **Professional appearance** - Clean, business-focused design
8. **Accessibility** - Clear focus states, readable sizes, good contrast
9. **Single-view interface** - All settings accessible without switching contexts

## Critical Implementation Notes

### Must-Have Features:
✅ Strict monochrome color palette (no exceptions)
✅ MA type selection via checkbox grid (not dropdown)
✅ Two collapsible sections (Stops and Filters, Trailing Stops)
✅ Parameter groups for related inputs
✅ No tab navigation
✅ Single scrollable content area
✅ Consistent spacing and borders
✅ Professional window chrome (title bar with controls)

### Must-Avoid:
❌ Any colored UI elements
❌ Tab navigation (Inputs/Properties/Style/Visibility)
❌ Dropdown menus for MA type selection
❌ Inconsistent spacing
❌ Multiple windows or dialogs
❌ Overly decorative elements

## Interaction Patterns

1. **Checkboxes**: Click to toggle, affect which MA types are tested
2. **Number inputs**: Click to focus, type value, or use arrow keys
3. **Collapsible headers**: Click to expand/collapse section
4. **Buttons**: 
   - "Run": Execute backtest with current parameters
   - "Cancel": Close window or reset
   - "Defaults": Reset all values to defaults
   - "📅": Open date picker (calendar widget)

## Implementation Flexibility

These guidelines are **framework-agnostic**. Adapt to your specific GUI library

The key is maintaining the visual design, layout structure, and interaction patterns regardless of underlying technology.
