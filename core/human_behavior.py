#!/usr/bin/env python3
"""Human-like interaction patterns to avoid bot detection"""

import random
import asyncio
from typing import Optional

class HumanBehavior:
    """Human-like interaction patterns - usable by all platform bots"""
    
    @staticmethod
    async def human_delay(min_ms: int = 800, max_ms: int = 3500, 
                          variation: float = 0.3) -> None:
        """Human-like delay with natural variation"""
        base_delay = random.uniform(min_ms, max_ms)
        # Add log-normal style variation (occasional longer pauses)
        if random.random() < 0.1:  # 10% chance of "thinking" pause
            base_delay *= random.uniform(1.5, 3.0)
        actual_delay = base_delay * random.uniform(1 - variation, 1 + variation)
        await asyncio.sleep(actual_delay / 1000)
    
    @staticmethod
    async def human_scroll(page, target_y: Optional[int] = None, 
                           duration_ms: int = 800) -> None:
        """Smooth, human-like scrolling with acceleration/deceleration"""
        if target_y is None:
            # Random scroll distance
            target_y = random.randint(200, 700)
        
        current_y = await page.evaluate("window.pageYOffset")
        steps = random.randint(12, 25)
        step_time = duration_ms / steps
        
        # Easing function for natural movement
        def ease_out_cubic(t):
            return 1 - (1 - t) ** 3
        
        for i in range(steps):
            t = i / steps
            eased = ease_out_cubic(t)
            new_y = current_y + (target_y - current_y) * eased
            await page.evaluate(f"window.scrollTo({{top: {new_y}, behavior: 'auto'}})")
            await asyncio.sleep(step_time / 1000)
        
        # Small overshoot sometimes (human behavior)
        if random.random() < 0.15:
            overshoot = random.randint(-30, 30)
            await page.evaluate(f"window.scrollBy(0, {overshoot})")
            await asyncio.sleep(random.uniform(0.1, 0.3))
    
    @staticmethod
    async def human_mouse_movement(page, selector: str = None, 
                                   target_x: int = None, target_y: int = None) -> None:
        """Move mouse with curved, non-linear path"""
        if selector:
            # Get element position
            bbox = await page.locator(selector).bounding_box()
            if not bbox:
                return
            target_x = bbox['x'] + bbox['width'] / 2
            target_y = bbox['y'] + bbox['height'] / 2
        elif target_x is None or target_y is None:
            return
        
        # Get current mouse position (approximate)
        current = await page.evaluate("() => ({x: window.mouseX || 500, y: window.mouseY || 300})")
        
        # Generate curved path
        steps = random.randint(8, 15)
        for i in range(steps):
            t = i / steps
            # Quadratic bezier with random control point
            cx = (current['x'] + target_x) / 2 + random.randint(-50, 50)
            cy = (current['y'] + target_y) / 2 + random.randint(-30, 30)
            
            x = (1-t)**2 * current['x'] + 2*(1-t)*t * cx + t**2 * target_x
            y = (1-t)**2 * current['y'] + 2*(1-t)*t * cy + t**2 * target_y
            
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.008, 0.025))
        
        # Store last position
        await page.evaluate(f"window.mouseX = {target_x}; window.mouseY = {target_y}")
    
    @staticmethod
    async def human_click(page, selector: str = None, 
                          x: int = None, y: int = None,
                          offset_px: int = 5) -> None:
        """Click with random offset from element center"""
        if selector:
            bbox = await page.locator(selector).bounding_box()
            if bbox:
                x = bbox['x'] + bbox['width'] / 2 + random.randint(-offset_px, offset_px)
                y = bbox['y'] + bbox['height'] / 2 + random.randint(-offset_px, offset_px)
            else:
                await page.click(selector)
                return
        
        if x and y:
            await page.mouse.click(x, y)
    
    @staticmethod
    async def human_typing(page, selector: str, text: str, 
                           typo_chance: float = 0.02) -> None:
        """Type with variable speed and occasional typos/backspaces"""
        await page.click(selector)
        await HumanBehavior.human_delay(200, 600)
        
        # Clear field with human-like backspacing or Ctrl+A
        if random.random() < 0.3:
            await page.keyboard.press("Control+A")
            await HumanBehavior.human_delay(50, 150)
            await page.keyboard.press("Backspace")
        else:
            current = await page.get_attribute(selector, "value") or ""
            for _ in range(len(current)):
                await page.keyboard.press("Backspace")
                await HumanBehavior.human_delay(30, 80)
        
        await HumanBehavior.human_delay(100, 300)
        
        for i, char in enumerate(text):
            # Occasional typo
            if random.random() < typo_chance and char.isalpha():
                # Type wrong character
                wrong_char = chr(ord(char) + random.choice([-1, 1]))
                await page.keyboard.type(wrong_char)
                await HumanBehavior.human_delay(80, 200)
                # Backspace and fix
                await page.keyboard.press("Backspace")
                await HumanBehavior.human_delay(100, 250)
            
            await page.keyboard.type(char)
            
            # Variable typing speed
            if char in ['.', ',', '!', '?', ';']:
                delay = random.uniform(200, 450)  # Pause at punctuation
            elif char == ' ':
                delay = random.uniform(60, 150)
            else:
                delay = random.uniform(40, 180)
            
            await asyncio.sleep(delay / 1000)
        
        # Sometimes pause at the end
        if random.random() < 0.2:
            await HumanBehavior.human_delay(400, 1000)
    
    @staticmethod
    async def random_micro_movements(page, duration_seconds: float = 2.0):
        """Make random tiny mouse movements (like a human's micro-adjustments)"""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < duration_seconds:
            # Small, almost imperceptible movements
            dx = random.randint(-5, 5)
            dy = random.randint(-3, 3)
            await page.mouse.move(
                (await page.evaluate("window.mouseX || 500")) + dx,
                (await page.evaluate("window.mouseY || 300")) + dy
            )
            await asyncio.sleep(random.uniform(0.5, 1.5))
