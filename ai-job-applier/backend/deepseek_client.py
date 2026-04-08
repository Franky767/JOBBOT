import os
import json
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class DeepSeekClient:
    """Cliente que intenta DeepSeek primero, luego Gemini como respaldo"""
    
    def __init__(self):
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.current_provider = "none"
        
        print("\n🔧 INICIALIZANDO CLIENTE API")
        print(f"   DeepSeek API Key: {'✅ Configurada' if self.deepseek_key else '❌ No configurada'}")
        print(f"   Gemini API Key: {'✅ Configurada' if self.gemini_key else '❌ No configurada'}")
    
    @property
    def using_gemini(self):
        return self.current_provider == "gemini"
    
    @property
    def using_deepseek(self):
        return self.current_provider == "deepseek"
    
    def generate(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        """Intenta DeepSeek primero, si falla usa Gemini"""
        
        # 1. Intentar con DeepSeek
        if self.deepseek_key:
            print("   🤖 Intentando con DeepSeek...")
            result = self._try_deepseek(prompt, temperature)
            if result:
                self.current_provider = "deepseek"
                return result
            print("   ⚠️ DeepSeek falló, probando Gemini...")
        
        # 2. Si DeepSeek falla, intentar con Gemini
        if self.gemini_key:
            print("   🤖 Intentando con Gemini...")
            result = self._try_gemini(prompt, temperature)
            if result:
                self.current_provider = "gemini"
                return result
        
        print("   ❌ Todas las APIs fallaron")
        return None
    
    def _try_deepseek(self, prompt: str, temperature: float) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.deepseek_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }
        
        # Add retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60  # Increased from 30 to 60 seconds
                )
                
                if response.status_code == 200:
                    print("   ✅ DeepSeek respondió OK")
                    return response.json()["choices"][0]["message"]["content"]
                else:
                    print(f"   ❌ DeepSeek error {response.status_code}: {response.text[:100]}")
                    
            except requests.exceptions.Timeout:
                print(f"   ⏱️ DeepSeek timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
                continue
            except Exception as e:
                print(f"   ❌ DeepSeek exception: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue
        
        return None

    def _try_gemini(self, prompt: str, temperature: float) -> Optional[str]:
        # Update to current Gemini model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=60)
            if response.status_code == 200:
                print("   ✅ Gemini respondió OK")
                result = response.json()
                return result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"   ❌ Gemini error {response.status_code}")
                return None
        except Exception as e:
            print(f"   ❌ Gemini exception: {e}")
            return None
