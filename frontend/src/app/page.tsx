import { ConnectionTest } from '@/components/ConnectionTest';

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-100 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            📚 Wiki Generator
          </h1>
          <p className="text-lg text-gray-600">
            Generate documentation for any public GitHub repository
          </p>
        </div>

        <div className="flex justify-center">
          <ConnectionTest />
        </div>

        <div className="mt-12 text-center text-sm text-gray-500">
          <p>Phase 0: Infrastructure skeleton</p>
        </div>
      </div>
    </main>
  );
}
