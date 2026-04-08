import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { Profile } from '@/lib/api';

export default function PersonaDetailsPage() {
  const router = useRouter();
  const { id } = router.query;
  const [persona, setPersona] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [reparseLoading, setReparseLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [jobs, setJobs] = useState<any[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  useEffect(() => {
    if (id) {
      loadPersona();
    }
  }, [id]);

  const loadPersona = async () => {
    try {
      const response = await fetch(`http://localhost:8000/profile/${id}`);
      const data = await response.json();
      setPersona(data);
    } catch (error) {
      console.error('Error loading persona:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCV = () => {
    if (persona && persona.resume_text) {
      const blob = new Blob([persona.resume_text], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${persona.name}_CV.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const handleReparse = async () => {
    if (!id) return;
    
    setReparseLoading(true);
    setMessage('');
    
    try {
      const response = await fetch(`http://localhost:8000/profile/${id}/reparse`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('Failed to re-parse CV');
      }
      
      const data = await response.json();
      setMessage('CV re-parsed successfully! Page will reload...');
      
      // Reload persona data
      setTimeout(() => {
        loadPersona();
        setMessage('');
      }, 1500);
    } catch (error: any) {
      console.error('Error re-parsing:', error);
      setMessage(`Error: ${error.message}`);
    } finally {
      setReparseLoading(false);
    }
  };

  const handleFetchJobs = async () => {
    setJobsLoading(true);
    setMessage('');
    
    // Build search criteria message
    const searchTitles = persona?.job_search_titles?.join(', ') || 'No titles specified';
    const location = persona?.city && persona?.country 
      ? `${persona.city}, ${persona.country}` 
      : persona?.country || 'Any location';
    const remote = persona?.remote_pct !== undefined ? `${persona.remote_pct}% remote` : 'Remote flexibility not specified';
    
    setMessage(`🔍 Searching for: ${searchTitles} | Location: ${location} | ${remote}`);
    
    try {
      const response = await fetch(`http://localhost:8000/jobs?profile_id=${id}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch jobs');
      }
      
      const data = await response.json();
      
      // Flatten jobs_by_search into a single array with search_query field
      const allJobs: any[] = [];
      if (data.jobs_by_search && Object.keys(data.jobs_by_search).length > 0) {
        Object.entries(data.jobs_by_search).forEach(([searchTitle, searchJobs]: [string, any]) => {
          (searchJobs as any[]).forEach(job => {
            allJobs.push({
              ...job,
              search_query: searchTitle
            });
          });
        });
        setJobs(allJobs);
        setMessage(`✅ Found ${data.total_found} total jobs from ${data.search_results?.length || 0} searches!`);
      } else {
        setJobs([]);
        const searchedTitles = data.search_results?.map((r: any) => r.title).join(', ') || 'your profile titles';
        setMessage(`⚠️ No jobs found for: ${searchedTitles}. Try updating your job search titles or location in the profile editor, or the Adzuna API may not have jobs matching these exact criteria in your location.`);
      }
    } catch (error: any) {
      console.error('Error fetching jobs:', error);
      setMessage(`❌ Error: ${error.message}`);
      setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!persona) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-4">Persona not found</p>
          <Link href="/" className="text-blue-600 hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">Persona Details</h1>
            <div className="flex gap-3">
              <Link href="/" className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700">
                Back to Home
              </Link>
              <Link href="/profile" className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Edit Profile
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {message && (
          <div className={`mb-4 p-3 rounded ${message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
            {message}
          </div>
        )}

        <div className="bg-white rounded-lg shadow overflow-hidden">
          {/* Header Section */}
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-8 text-white">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-3xl font-bold mb-2">{persona.name}</h2>
                {persona.is_active && (
                  <span className="inline-block px-3 py-1 bg-green-500 text-white text-sm rounded-full">
                    Active Persona
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {persona.resume_text && (
                  <button
                    onClick={handleDownloadCV}
                    className="px-4 py-2 bg-white text-blue-600 rounded-md hover:bg-gray-100 font-medium"
                  >
                    Download CV
                  </button>
                )}
                {persona.resume_text && (
                  <button
                    onClick={handleReparse}
                    disabled={reparseLoading}
                    className="px-4 py-2 bg-yellow-500 text-white rounded-md hover:bg-yellow-600 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {reparseLoading ? 'Re-parsing...' : 'Parse Again'}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Job Search Titles - Prominent Section */}
          {persona.job_search_titles && persona.job_search_titles.length > 0 && (
            <div className="p-6 border-b bg-yellow-50">
              <h3 className="text-xl font-semibold mb-2 text-gray-900">🔍 Job Search Titles</h3>
              <p className="text-sm text-gray-600 mb-3">These titles will be used when searching for jobs:</p>
              <div className="flex flex-wrap gap-2">
                {persona.job_search_titles.map((title, idx) => (
                  <span key={idx} className="px-4 py-2 bg-yellow-200 text-yellow-900 rounded-lg font-semibold text-base">
                    {title}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Personal Information */}
          <div className="p-6 border-b">
            <h3 className="text-xl font-semibold mb-4 text-gray-900">Personal Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-500">First Name</label>
                <p className="mt-1 text-gray-900">{persona.first_name || 'Not provided'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Last Name</label>
                <p className="mt-1 text-gray-900">{persona.last_name || 'Not provided'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Email</label>
                <p className="mt-1 text-gray-900">{persona.email || 'Not provided'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Phone</label>
                <p className="mt-1 text-gray-900">{persona.phone || 'Not provided'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">City</label>
                <p className="mt-1 text-gray-900">{persona.city || 'Not provided'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Country</label>
                <p className="mt-1 text-gray-900">{persona.country || 'Not provided'}</p>
              </div>
            </div>
          </div>

          {/* Professional Links */}
          <div className="p-6 border-b">
            <h3 className="text-xl font-semibold mb-4 text-gray-900">Professional Links</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-500">LinkedIn</label>
                <p className="mt-1">
                  {persona.linkedin ? (
                    <a href={persona.linkedin} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {persona.linkedin}
                    </a>
                  ) : (
                    <span className="text-gray-900">Not provided</span>
                  )}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">GitHub</label>
                <p className="mt-1">
                  {persona.github ? (
                    <a href={persona.github} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {persona.github}
                    </a>
                  ) : (
                    <span className="text-gray-900">Not provided</span>
                  )}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Portfolio</label>
                <p className="mt-1">
                  {persona.portfolio ? (
                    <a href={persona.portfolio} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {persona.portfolio}
                    </a>
                  ) : (
                    <span className="text-gray-900">Not provided</span>
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Job Titles */}
          {persona.titles && persona.titles.length > 0 && (
            <div className="p-6 border-b">
              <h3 className="text-xl font-semibold mb-4 text-gray-900">Job Titles</h3>
              <div className="flex flex-wrap gap-2">
                {persona.titles.map((title, idx) => (
                  <span key={idx} className="px-3 py-2 bg-blue-100 text-blue-800 rounded-lg font-medium">
                    {title}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Skills */}
          {persona.skills && persona.skills.length > 0 && (
            <div className="p-6 border-b">
              <h3 className="text-xl font-semibold mb-4 text-gray-900">Skills</h3>
              <div className="flex flex-wrap gap-2">
                {persona.skills.map((skill, idx) => (
                  <span key={idx} className="px-3 py-2 bg-green-100 text-green-800 rounded-lg text-sm">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Work Preferences */}
          <div className="p-6 border-b">
            <h3 className="text-xl font-semibold mb-4 text-gray-900">Work Preferences</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-500">Work Authorization</label>
                <p className="mt-1 text-gray-900">{persona.work_auth || 'Not specified'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Remote Percentage</label>
                <p className="mt-1 text-gray-900">{persona.remote_pct !== undefined ? `${persona.remote_pct}%` : 'Not specified'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Notice Period</label>
                <p className="mt-1 text-gray-900">{persona.notice_period_days ? `${persona.notice_period_days} days` : 'Not specified'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500">Salary Range</label>
                <p className="mt-1 text-gray-900">
                  {persona.salary_min && persona.salary_max 
                    ? `$${persona.salary_min.toLocaleString()} - $${persona.salary_max.toLocaleString()}`
                    : 'Not specified'}
                </p>
              </div>
            </div>
          </div>

          {/* Preferred Locations */}
          {persona.preferred_locations && persona.preferred_locations.length > 0 && (
            <div className="p-6 border-b">
              <h3 className="text-xl font-semibold mb-4 text-gray-900">Preferred Locations</h3>
              <div className="flex flex-wrap gap-2">
                {persona.preferred_locations.map((location, idx) => (
                  <span key={idx} className="px-3 py-2 bg-gray-100 text-gray-800 rounded-lg">
                    {location}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Resume */}
          <div className="p-6 border-b">
            <h3 className="text-xl font-semibold mb-4 text-gray-900">Resume</h3>
            <div>
              <label className="block text-sm font-medium text-gray-500">Resume Path</label>
              <p className="mt-1 text-gray-900 break-all">{persona.resume_path || 'No resume uploaded'}</p>
            </div>
          </div>

          {/* Metadata */}
          <div className="p-6 bg-gray-50">
            <h3 className="text-xl font-semibold mb-4 text-gray-900">Metadata</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <label className="block font-medium text-gray-500">Persona ID</label>
                <p className="mt-1 text-gray-900">{persona.id}</p>
              </div>
              <div>
                <label className="block font-medium text-gray-500">Status</label>
                <p className="mt-1 text-gray-900">{persona.is_active ? 'Active' : 'Inactive'}</p>
              </div>
              {persona.created_at && (
                <div>
                  <label className="block font-medium text-gray-500">Created At</label>
                  <p className="mt-1 text-gray-900">{new Date(persona.created_at).toLocaleString()}</p>
                </div>
              )}
              {persona.updated_at && (
                <div>
                  <label className="block font-medium text-gray-500">Last Updated</label>
                  <p className="mt-1 text-gray-900">{new Date(persona.updated_at).toLocaleString()}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Fetch Jobs Section */}
        <div className="bg-white rounded-lg shadow p-6 mt-8">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Job Search</h2>
            <button
              onClick={handleFetchJobs}
              disabled={jobsLoading}
              className="px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {jobsLoading ? 'Searching...' : 'Fetch Jobs'}
            </button>
          </div>

          {jobs.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No jobs loaded yet. Click "Fetch Jobs" to search based on this persona's profile.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Job Title</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Company</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Search Query</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Link</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {jobs.map((job: any) => (
                    <tr key={job.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <div className="text-sm font-medium text-gray-900">{job.title}</div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="text-sm text-gray-600">{job.company}</div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                          {job.search_query}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center"
                        >
                          View Job
                          <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      </td>
                      <td className="px-4 py-4">
                        <Link
                          href={`/?job=${job.id}`}
                          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 inline-block"
                        >
                          Apply
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
