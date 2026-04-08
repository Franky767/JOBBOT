import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { uploadCv, getAllProfiles, activateProfile, Profile } from '@/lib/api';

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvText, setCvText] = useState('');
  const [personas, setPersonas] = useState<Profile[]>([]);
  const [activePersona, setActivePersona] = useState<Profile | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    try {
      const allPersonas = await getAllProfiles();
      setPersonas(allPersonas);
      const active = allPersonas.find(p => p.is_active);
      setActivePersona(active || null);
    } catch (error) {
      console.error('Error loading personas:', error);
    }
  };

  const handlePersonaChange = async (personaId: number) => {
    try {
      await activateProfile(personaId);
      await loadPersonas();
      setMessage('Persona switched successfully!');
    } catch (error) {
      console.error('Error switching persona:', error);
      setMessage('Error switching persona');
    }
  };

  const handleUploadCv = async () => {
    if (!cvFile && !cvText.trim()) {
      setMessage('Please provide a CV file or paste CV text');
      return;
    }

    setLoading(true);
    setMessage('');
    try {
      await uploadCv(cvFile || undefined, cvText || undefined);
      setMessage('CV uploaded and persona created successfully!');
      setCvFile(null);
      setCvText('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      // Reload personas
      await loadPersonas();
    } catch (error) {
      console.error('Error uploading CV:', error);
      setMessage('Error uploading CV');
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">AI Job Applier</h1>
            <div className="flex gap-3">
              <Link href="/settings" className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700">
                Settings
              </Link>
              <Link href="/profile" className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Edit Profile
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Persona Selector */}
        {personas.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-8">
            <h2 className="text-xl font-bold mb-4">Active Persona</h2>
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Persona
                </label>
                <select
                  value={activePersona?.id || ''}
                  onChange={(e) => handlePersonaChange(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {personas.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name} {p.is_active && '(Active)'}
                    </option>
                  ))}
                </select>
              </div>
              <Link
                href={`/persona/${activePersona?.id}`}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 text-center"
              >
                View Details
              </Link>
            </div>
          </div>
        )}

        {/* CV Upload Section */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Upload Your CV</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Upload CV File (PDF, DOCX, or TXT)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setCvFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Or Paste CV Text</label>
              <textarea
                value={cvText}
                onChange={(e) => setCvText(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Paste your CV text here..."
              />
            </div>
            <button
              onClick={handleUploadCv}
              disabled={loading}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Uploading...' : 'Upload & Parse CV'}
            </button>
          </div>
        </div>

      </main>
    </div>
  );
}
