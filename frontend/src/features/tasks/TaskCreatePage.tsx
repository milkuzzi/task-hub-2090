import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';
import { errorMessage } from '@/shared/api/http';
import type { CreateTaskInput } from '@/shared/types';
import TaskForm from './TaskForm';

export default function TaskCreatePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ input, files }: { input: CreateTaskInput; files: File[] }) =>
      api.createTask(input, files),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      navigate('/tasks/' + created.id);
    },
  });

  return (
    <div>
      <h1>{STR.addTask}</h1>
      <TaskForm
        submitLabel={STR.save}
        allowAttachments
        onSubmit={(input, files) => mutation.mutate({ input, files })}
        busy={mutation.isPending}
        error={mutation.isError ? errorMessage(mutation.error) : ''}
      />
    </div>
  );
}
