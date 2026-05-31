import { redirect } from 'next/navigation';

// Rota legada — JUNO unificou todas as empresas em "Minha Empresa" (/romi).
// Mantida apenas para não quebrar bookmarks/links antigos.
export default function FachiniLegacyRedirect() {
  redirect('/romi');
}
