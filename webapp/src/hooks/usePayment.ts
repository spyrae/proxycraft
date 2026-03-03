import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { openInvoice } from '@telegram-apps/sdk-react';
import { openLink } from '@telegram-apps/sdk';
import { useCreateInvoice } from '../api/hooks';

type PaymentStatus = 'idle' | 'loading' | 'paid' | 'cancelled' | 'failed' | 'pending_external';

interface UsePaymentOptions {
  product: 'vpn' | 'mtproto' | 'whatsapp';
  devices?: number;
  duration: number;
  is_extend?: boolean;
  currency?: 'stars' | 'rub';
}

export function usePayment() {
  const createInvoice = useCreateInvoice();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<PaymentStatus>('idle');

  const pay = useCallback(
    async (opts: UsePaymentOptions) => {
      setStatus('loading');

      try {
        const response = await createInvoice.mutateAsync({
          product: opts.product,
          devices: opts.devices,
          duration: opts.duration,
          is_extend: opts.is_extend,
          currency: opts.currency,
        });

        // T-Bank payment: open external payment URL
        if (response.payment_url) {
          openLink(response.payment_url, { tryBrowser: 'chrome' });
          setStatus('pending_external');
          // Invalidate queries after delay so data refreshes when user returns
          setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ['me'] });
            queryClient.invalidateQueries({ queryKey: ['subscription'] });
          }, 5000);
          return 'pending';
        }

        // Stars payment: open Telegram invoice
        if (response.invoice_url) {
          const result = await openInvoice(response.invoice_url, 'url');

          if (result === 'paid') {
            setStatus('paid');
            queryClient.invalidateQueries({ queryKey: ['me'] });
            queryClient.invalidateQueries({ queryKey: ['subscription'] });
          } else if (result === 'cancelled') {
            setStatus('cancelled');
          } else {
            setStatus('failed');
          }

          return result;
        }

        setStatus('failed');
        return 'failed';
      } catch (err) {
        setStatus('failed');
        throw err;
      }
    },
    [createInvoice, queryClient],
  );

  return { pay, status, isLoading: status === 'loading' };
}
